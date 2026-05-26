// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {NAVOracle} from "../src/NAVOracle.sol";
import {IndexToken} from "../src/IndexToken.sol";
import {CCTPRouter} from "../src/CCTPRouter.sol";
import {USYCParkVault} from "../src/USYCParkVault.sol";
import {RebalanceExecutor} from "../src/RebalanceExecutor.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {MockUSYC} from "../src/mocks/MockUSYC.sol";
import {MockTokenMessengerV2} from "../src/mocks/MockTokenMessengerV2.sol";

/// Deploys the WhaleIndex stack against Arc testnet.
///
/// Address resolution priority for each external dependency:
///   USDC:        $USDC_ADDRESS          → fall back to MockUSDC
///   TokenMsg:    $TOKEN_MESSENGER       → fall back to MockTokenMessengerV2
///   USYC:        $USYC_ADDRESS          → fall back to MockUSYC
///
/// Arc-testnet canonical addresses (set these in env before broadcasting):
///   USDC_ADDRESS=0x3600000000000000000000000000000000000000        (native USDC ERC-20 interface)
///   TOKEN_MESSENGER=0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA     (CCTP V2 TokenMessenger)
///   USYC_ADDRESS=<unset until Teller allowlist approved>           (falls back to MockUSYC)
contract DeployScript is Script {
    // CCTP V2 destination domains (verified 2026-05-17 from Circle docs).
    uint32 constant DOMAIN_ARBITRUM = 3;
    uint32 constant DOMAIN_SOLANA   = 5;

    // Demo seeding (testnet only). See the seeding block in run() for rationale.
    uint64  constant DEMO_FRESHNESS_WINDOW = 30 days;   // keep buy/redeem live across judging
    uint256 constant INITIAL_NAV_USDC      = 1_000_000; // 1.00 USDC baseline share price

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer    = vm.addr(deployerKey);
        address operator    = vm.envOr("OPERATOR_ADDRESS", deployer);

        vm.startBroadcast(deployerKey);

        // ---- External dependency resolution ----
        address usdcAddr      = vm.envOr("USDC_ADDRESS",    address(0));
        address messengerAddr = vm.envOr("TOKEN_MESSENGER", address(0));
        address usycAddr      = vm.envOr("USYC_ADDRESS",    address(0));

        if (usdcAddr == address(0)) {
            usdcAddr = address(new MockUSDC());
            console.log("  USDC source: MockUSDC (deployed fresh)");
        } else {
            console.log("  USDC source: REAL (from env)");
        }

        if (messengerAddr == address(0)) {
            messengerAddr = address(new MockTokenMessengerV2());
            console.log("  TokenMessenger source: MockTokenMessengerV2 (deployed fresh)");
        } else {
            console.log("  TokenMessenger source: REAL (from env)");
        }

        if (usycAddr == address(0)) {
            usycAddr = address(new MockUSYC(usdcAddr));
            console.log("  USYC source: MockUSYC (deployed fresh - Teller allowlist pending)");
        } else {
            console.log("  USYC source: REAL (from env)");
        }

        // ---- Core protocol stack ----
        NAVOracle nav = new NAVOracle(operator);

        uint32[] memory domains = new uint32[](2);
        domains[0] = DOMAIN_ARBITRUM;
        domains[1] = DOMAIN_SOLANA;
        CCTPRouter router = new CCTPRouter(usdcAddr, messengerAddr, domains);

        USYCParkVault park = new USYCParkVault(usdcAddr, usycAddr, deployer);
        IndexToken   index = new IndexToken(usdcAddr, address(nav), deployer);

        RebalanceExecutor exec = new RebalanceExecutor(
            usdcAddr,
            address(index),
            address(nav),
            address(router),
            address(park),
            operator,
            500 * 1e6,    // maxSingleMove = 500 USDC
            10_000 * 1e6  // dailyCap = 10,000 USDC
        );

        index.transferOwnership(address(exec));
        park.transferOwnership(address(exec));

        // Single-key setup: deployer == operator, so NAV ownership transfers
        // in the same broadcast. Two-key setup leaves NAV owned by `operator`.
        if (operator == deployer) {
            // Demo seeding (testnet only): while the deployer still owns the
            // oracle, widen the freshness window and seed an initial NAV so the
            // public buy/redeem path is live the moment the stack is deployed,
            // WITHOUT fabricating a rebalance trade to warm the oracle.
            //
            // PRODUCTION NOTE: a real deployment keeps freshnessWindow short
            // (~60s, the constructor default) and runs an operator NAV heartbeat.
            // The long window here reflects that this testnet NAV is intentionally
            // static — the agent is in a published HOLD state, so NAV does not move.
            nav.setFreshnessWindow(DEMO_FRESHNESS_WINDOW);
            nav.updateNAV(INITIAL_NAV_USDC, uint64(block.timestamp));
            nav.transferOwnership(address(exec));
        }

        vm.stopBroadcast();

        console.log("Deployed addresses:");
        console.log("  USDC:              ", usdcAddr);
        console.log("  USYC:              ", usycAddr);
        console.log("  TokenMessenger:    ", messengerAddr);
        console.log("  NAVOracle:         ", address(nav));
        console.log("  CCTPRouter:        ", address(router));
        console.log("  USYCParkVault:     ", address(park));
        console.log("  IndexToken:        ", address(index));
        console.log("  RebalanceExecutor: ", address(exec));
    }
}
