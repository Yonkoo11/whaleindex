// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Minimal Paymaster sponsorship hook. Real Circle Paymaster is ERC-4337-shaped;
// V1 calls a sponsor hook so the contract emits an on-chain marker that a paymaster
// would have covered the gas. Swap to the live Paymaster address when published.
interface IPaymaster {
    function sponsor(address user, bytes calldata callData) external;
}
