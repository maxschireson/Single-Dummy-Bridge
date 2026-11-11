"""One spawned BEN board per process, with parent-observed exit status.

No retry and no changes to the supplied initializer, task, arguments or RNG.
The Future completes only after the child exits successfully. At most one
child exists at a time; the persistent BEN HTTP server is owned by the launcher.
"""
from concurrent.futures import Executor, Future
from concurrent.futures.process import BrokenProcessPool
import multiprocessing as mp
import signal
import threading
import time
import traceback
from ops.diagnostic_supervisor import Recorder, memory_snapshot, process_snapshot


def _one_board(connection, initializer, initargs, function, args, kwargs):
    try:
        initializer(*initargs)
        result = function(*args, **kwargs)
        connection.send(('ok', result))
    except BaseException:
        connection.send(('error', traceback.format_exc()))
        raise
    finally:
        connection.close()


class BenBoardExecutor(Executor):
    def __init__(self, run, initializer, initargs):
        self.context = mp.get_context('spawn')
        self.initializer, self.initargs = initializer, initargs
        self.recorder = Recorder(run, 'ben-board-worker')
        self.closed = False
        self.future = None
        self.thread = None
        self.guard = threading.Lock()

    def submit(self, function, /, *args, **kwargs):
        with self.guard:
            if self.closed:
                raise RuntimeError('BEN executor is shut down')
            if self.future is not None and not self.future.done():
                raise RuntimeError('BEN lane already has a board')
            receiver, sender = self.context.Pipe(duplex=False)
            process = self.context.Process(target=_one_board,
                args=(sender, self.initializer, self.initargs, function, args, kwargs))
            future = Future()
            future.set_running_or_notify_cancel()
            self.future = future
            try:
                process.start()
            except BaseException:
                receiver.close(); sender.close()
                raise
            sender.close()
            self.recorder.emit('worker-start', pid=process.pid,
                index=args[-1] if args and isinstance(args[-1], int) else None,
                resources=memory_snapshot(), max_boards=1)
            self.thread = threading.Thread(target=self._observe,
                args=(process, receiver, future), daemon=False)
            self.thread.start()
            return future

    def _observe(self, process, receiver, future):
        message = None
        error = None
        last_sample = 0
        try:
            while process.is_alive():
                if message is None and receiver.poll(.25):
                    try:
                        message = receiver.recv()
                    except EOFError:
                        pass
                else:
                    process.join(.25)
                if time.monotonic() - last_sample >= 5:
                    self.recorder.emit('resources', worker=process_snapshot(process.pid),
                        resources=memory_snapshot())
                    last_sample = time.monotonic()
            process.join()
            if message is None and receiver.poll():
                try:
                    message = receiver.recv()
                except EOFError:
                    pass
        except BaseException as exc:
            error = exc
            if process.is_alive():
                process.terminate()
            process.join()
        finally:
            code = process.exitcode
            self.recorder.emit('worker-exit', pid=process.pid, exitcode=code,
                signal=signal.Signals(-code).name if code is not None and code < 0 else None,
                resources=memory_snapshot(), result_received=message is not None,
                note='Signals alone do not establish OOM; no automatic retry.')
            receiver.close()
            process.close()
        if error is not None:
            future.set_exception(error)
        elif code != 0 or message is None or message[0] != 'ok':
            detail = message[1] if message and message[0] == 'error' else 'missing successful result'
            future.set_exception(BrokenProcessPool(f'BEN worker exited {code}: {detail}'))
        else:
            future.set_result(message[1])

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self.guard:
            self.closed = True
            thread = self.thread
        if wait and thread is not None:
            thread.join()
