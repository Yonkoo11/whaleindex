# Security

## Keys never live in this repo

The deployer private key, operator private key, and Arc RPC key live ONLY in `~/.zshenv` on the operator's machine. They are loaded into the shell environment at session start and consumed at runtime by Foundry (`vm.envUint("DEPLOYER_PRIVATE_KEY")`) and the Python agent (`os.getenv("OPERATOR_PRIVATE_KEY")`).

Hard rules for everyone (and every AI agent) working on this repo:

1. **Never read `~/.zshenv` or any shell-rc file.** Not with `cat`, `grep`, `head`, `tail`, `Read`, or any other tool. Globally enforced by the project's PreToolUse hook.
2. **Never print key values.** Not in bash, not in Python, not in tests, not in logs. `print(os.getenv("KEY"))` is banned.
3. **Never commit `.env`** — covered by `.gitignore`, but verify with `git diff --cached` before every commit.
4. **Never use `git add -A`** for the first commit of a new file that might contain a key. Add files by explicit name.
5. **Foundry broadcasts must use the env-var key reference**, never a hardcoded value. The `Deploy.s.sol` script uses `vm.envUint("DEPLOYER_PRIVATE_KEY")` which reads from the process env at runtime, not from any file.
6. **If a key is ever pasted into a chat, the operator must rotate it immediately.** Don't continue the session "carefully" — rotate, then continue.
7. **Foundry `broadcast/` artifacts** sometimes contain the deployer address but not the key. Still inspect before pushing if you ever flip them out of `.gitignore`.

## Operator wallet (Wallets SDK policy)

The `RebalanceExecutor` enforces an on-chain spending policy: `maxSingleMove` and `dailyCap`. Even if the operator key is compromised, the blast radius is bounded by these caps. Default deployment values:

| Param | V1 testnet | Mainnet (proposed V2) |
|---|---|---|
| `maxSingleMove` | 500 USDC | 50,000 USDC |
| `dailyCap` | 10,000 USDC | 250,000 USDC |
| Operator multisig | single-sig | 2/3 multisig via Wallets SDK |

## What to do if you suspect a leak

1. Stop. Don't continue any tool calls that touch keys.
2. Rotate the leaked key on the source (re-issue from Privy/Turnkey/wallet).
3. Generate a fresh operator address and call `RebalanceExecutor.transferOwnership(newOperator)` from the old one (if it still has access) OR pause via emergency social recovery.
4. Update `~/.zshenv` with the new key (the operator does this manually, NOT an AI).
5. File an incident note in `ai/incidents/YYYY-MM-DD-leak.md` so the postmortem is captured.
