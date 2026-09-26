# live/

## Why a smaller socket

`LiveSocket` follows sridhara's, with the subscription modes, order updates and notifications taken out. The explorer has one kind of subscription and no account. It counts how many components retain each instrument and tells the server only about instruments newly watched or no longer watched. It reconnects with backoff from 1 to 15 seconds, and checks whether the session ended when the socket closes.

## The quote store

`QuoteStore` ignores a quote older than the one it holds, because the REST quote and the first live batch can arrive in either order. It drops an instrument's quote when its last listener leaves.

## useLiveQuote

`useLiveQuote` loads the quote over REST once, for instruments the live feed does not cover or when the market is closed, then retains the instrument on the socket for as long as the component is shown.
