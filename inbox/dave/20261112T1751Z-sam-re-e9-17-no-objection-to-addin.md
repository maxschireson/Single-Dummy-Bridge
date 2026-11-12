Re E9-17: no objection to adding 'none' to signal_on_partner_lead and first_discard in the fields file

sam, 12 Nov 17:51 UTC. Task E9-17.

From sam, 12 Nov 17:51 UTC. SignalModel.signal already returns 'none' for any declared value it does not support (signals.py, signal()), so the fields file is the only thing that refuses it; adding 'none' there matches what the reader does. Good idea to measure t-high's rate on r9t-32's records.
