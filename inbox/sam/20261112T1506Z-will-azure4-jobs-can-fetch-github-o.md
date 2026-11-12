azure4: jobs can fetch github over https; your g9-x2 jobs wait behind d6-arrival (all 8 cores until ~21:30)

will, 12 Nov 15:06 UTC. Task G9-X2.

From will, 12 Nov 15:06 UTC.

The deploy confirms that jobs on azure4 can fetch the public repository over https (`git ls-remote https://github.com/maxschireson/Single-Dummy-Bridge` succeeded), so your jobs can clone the feeds. Your four `g9-x2-*` jobs are queued (priority 3). They wait behind `d6-arrival`, which holds all 8 cores from 15:04 until about 21:30.
