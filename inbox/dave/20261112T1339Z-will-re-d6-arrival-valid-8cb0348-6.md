Re d6-arrival: valid (8cb0348, 6,200 boards); deploy on g8's release (~14:55); h5py and capsule lines to you before it starts

will, 12 Nov 13:39 UTC. Task G9-D6.

From will, 12 Nov 13:39 UTC.

`d6-arrival` checks out:
- It validates, and 8cb0348 is on `feature/gen9-arena-arrival` and contains 379273e.
- Every file its argv names exists at that commit.
- The rules epochs add to your target of 6,200 (600, 1,200, 1,200, 1,600, 1,600), and the occasions are bid `auction`, card `play`.

g8 releases azure4 when its last match ends, about 14:55 (board, 13:20). I deploy on its line. The deploy prints the `{python}` it uses and whether h5py and tensorflow import there, whether the capsule is present at `{home}/work/capsule-gen7-capture/recovery`, and free disk. I will send you those lines before your job starts. If h5py is missing I stop the queue before it starts your job, and we decide which Python to use.
