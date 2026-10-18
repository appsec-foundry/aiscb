The local CLI currently displays every transport event as "Transport error".
Improve display.py so retry progress and a final failure are distinguishable,
show the attempt count as current/maximum, and retain the useful explanation
already provided by transport.admit_event. The CLI is used by the project
operator. Keep the existing admission path and run python3 -m unittest -v.
