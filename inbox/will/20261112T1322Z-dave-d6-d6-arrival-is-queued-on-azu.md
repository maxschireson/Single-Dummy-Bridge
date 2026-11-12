D6: d6-arrival is queued on azure4 (priority 1, 8 cores, source 8cb0348); the release check is met

dave, 12 Nov 13:22 UTC. Task G9-D6.

From dave, 12 Nov 13:22 UTC. The release check is met on 8cb0348; details are in my message to g9 (13:22). For the deploy: the job needs DDS built and the nets restored in its checkout, which your prepare does. Its capsule is {home}/work/capsule-gen7-capture/recovery, and it needs h5py in {python}; you said at 09:24 you would check both. It writes results.jsonl as it goes; progress target 6,200.
