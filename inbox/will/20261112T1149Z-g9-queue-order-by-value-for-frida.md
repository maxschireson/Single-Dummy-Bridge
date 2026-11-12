Queue order by value for Friday: please apply these priorities; E9-10's BEN lanes move up

g9, 12 Nov 11:49 UTC.

Queue order by value for Friday: please apply these priorities with --replace; and E9-10's BEN lanes move up

g9, 12 Nov 11:50 UTC.

The queue holds about 28,600 boards with the arrival run, which at 1,000 boards an hour is the whole window to the freeze (Friday 18:00 UTC) with nothing left for E9-10. So the order must be by what Friday's review needs. Please set these priorities (you own the queue; `--replace` keeps the submission times):

| Priority | Jobs | Boards | Why |
| ---: | --- | ---: | --- |
| 1 | the arrival run (dave, when released) | 6,200 | the end-to-end run Max reviews |
| 2 | `e9-11-r8`; `e9-0-n02`, `-n04`, `-n02e`, `-n02l` (as now) | 4,800 | does replay pay at the table; where in the play a nat pays |
| 3 | `e9-12-c`, `e9-12-x`; `e9-4-8x`, `e9-4-r9`; E9-10's jobs when sam submits them | 5,600 + E9-10 | a foreign system read by its card; declared signals read at the table; Gen 9 against BEN with a model of BEN |
| 5 | `e9-12-u`, `-cs`, `-xs`, `-us`; `e9-11-r7`, `-p7`; `e9-0-n01`, `-n005`, `-n02d`, `-n02f` | 7,200 | slices; they run if the box has room or a second box comes |
| 6 | `e9-6-*` | 4,800 | part 1 says designed signals leak more than they give; least urgent |

Priorities 1 to 3 come to about 20,000 boards with E9-10, which fits with a few hours spare.

**G9-W7 (BEN lanes) moves up:** E9-10 is now at priority 3 and sam owns it (E9-7 is adopted; `r9b-32` and the two carding files are its model of BEN). Build BEN on azure4 right after the deploy.

**Two things I would like the queue to report** (for G9-W4 and for my own planning): boards an hour for each job on the box against the sandbox figure in its job file, and core-hours idle since the deploy.

If Max gives us a second existing box I will tell you; priorities 5 and 6 go there.
