# Luma Application — Agora Agents Hackathon

Copy each block into the matching field on https://luma.com/7i50p2r9

---

## What is the passphrase?

SITEx1313

---

## What is your time zone? (We need this to coordinate Zoom times)

WAT (UTC+1), Lagos

---

## What are your social handles (X, TG, Discord, Github)? *

x: @yonkoo11 · tg: @yonkoo11 · discord: yonkoo11 · github: github.com/yonkoo11

---

## What are you most excited to build on Arc at this event? *

building a whale-migration index. agent watches HL, aster and polynomial leaderboards and rebalances usdc exposure across the forks based on where smart money is actually trading right now. on every other chain the gas eats the NAV before you can rebalance more than monthly.

what gets me about arc is gateway nanopayments + usdc-as-gas. finally lets the agent rebalance weekly (or per block if i go crazy) without bleeding the index dry. usyc parks idle usdc between rebalances, paymaster covers the buyer flow so retail never sees native gas. excited to actually use the stack the way it was built and not just deploy a contract and call it a day.

---

## What is one project that you've built that you're the most proud of?

trust oracle for x402 endpoints. cron probes a registry of x402 endpoints with real micropayments, scores them on uptime, latency and payload correctness, exposes a feed. stops agents from routing trades through dead or flaky endpoints.

server on render, 42 unit + 10 integration tests, 8 endpoints probed live with real coinbase x402 payments during world x coinbase, xmtp agent layer on top. spent way too long on the probe state machine but it's the cleanest piece of infra ive shipped.

---

## We welcome teams! Are there some folks you want to hack with? If so, please list their names + socials here.

solo on this one. happy to swap notes with anyone building on gateway or usyc though, those two feel under-explored compared to the rest of the stack.

---

## Alternate "most proud" answer (swap if you prefer)

LP Intel — concentrated liquidity analyzer for uniswap, sushi and pancake v3 across 4 chains. paste a wallet, get a per-position breakdown of cost basis, fee income and IL per tick range. every other tool fakes it at the pool level, the per-tick math is the actual moat.

shipped through build x season 2 with a remotion demo i built myself, which was honestly harder than the analyzer math.
