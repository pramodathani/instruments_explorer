# quote_snapshot_reader.py

A chain needs up to about 540 quotes at once, and a surface up to 16 chains' worth. Reading them with HMGET from ubi's live hash takes about 5 ms for a NIFTY expiry. One REST quote call per contract would take seconds, and could send ubi to a broker for every contract whose cached quote is older than five minutes.

A Redis failure returns an empty dictionary instead of raising, so a chain still renders its strikes, with dashes for prices, when ubi's Redis is briefly unreachable. The file is on the read-only guard's list of files allowed to touch ubi's stores, and it only reads.
