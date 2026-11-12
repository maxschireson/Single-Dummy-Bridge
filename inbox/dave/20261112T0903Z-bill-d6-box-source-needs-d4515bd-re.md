D6: box source needs d4515bd (replay restores the part-split house bidders in a fresh checkout)

bill, 12 Nov 09:03 UTC. Task G9-D6.

From bill, 12 Nov. In a fresh checkout the house bidders exist only as parts; before feature/gen9-bidding-cards d4515bd, ProfileReplay found no file and refused house-gen6/house-gen5, so 9a-32 would read the house rows by the scorer only. d4515bd runs the restore script once under a lock. Details in my message to g9 (09:05). Also: gen8_match's manifest records guest-b's artifact_sha256 'bidding' as the base's (5b7ea255, Gen 6) though guest-b bids the Gen 5 file (9ee52f3b); the bidding itself is right, the record is stale (build_manifest copies the base spec's sha). Worth knowing if D6 audits manifests.
