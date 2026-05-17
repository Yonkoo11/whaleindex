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

/// Deploys the full WhaleIndex stack against Arc testnet.
/// Uses mocks for USDC, USYC, and CCTP TokenMessenger until Circle publishes
/// the canonical Arc-testnet addresses. Swap addresses in the env vars when live.
contract DeployScript is Script {
    // CCTP V2 destination domains (verified 2026-05-17 from Circle docs).
    uint32 constant DOMAIN_ARBITRUM = 3;
    uint32 constant DOMAIN_SOLANA   = 5;

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address operator   = vm.envAddress("OPERATOR_ADDRESS");
        address deployer   = vm.addr(deployerKey);

        vm.startBroadcast(deployerKey);

        // Mock dependencies (replace with live addresses when Canteen publishes).
        MockUSDC usdc = new MockUSDC();
        MockUSYC usyc = new MockUSYC(address(usdc));
        MockTokenMessengerV2 messenger = new MockTokenMessengerV2();

        // Core protocol stack.
        NAVOracle nav = new NAVOracle(operator);

        uint32[] memory domains = new uint32[](2);
        domains[0] = DOMAIN_ARBITRUM;
        domains[1] = DOMAIN_SOLANA;
        CCTPRouter router = new CCTPRouter(address(usdc), address(messenger), domains);

        // Park and Index temporarily owned by deployer for ownership wiring.
        USYCParkVault park = new USYCParkVault(address(usdc), address(usyc), deployer);
        IndexToken index = new IndexToken(address(usdc), address(nav), deployer);

        RebalanceExecutor exec = new RebalanceExecutor(
            address(usdc),
            address(index),
            address(nav),
            address(router),
            address(park),
            operator,
            500 * 1e6,           // maxSingleMove = 500 USDC
            10_000 * 1e6         // dailyCap = 10,000 USDC
        );

        // Hand control to the executor.
        index.transferOwnership(address(exec));
        park.transferOwnership(address(exec));

        // NAVOracle currently owned by `operator`; operator transfers ownership separately
        // via a tx after deployment, since we can't impersonate the operator from this script.

        vm.stopBroadcast();

        console.log("Deployed addresses:");
        console.log("  USDC (mock):       ", address(usdc));
        console.log("  USYC (mock):       ", address(usyc));
        console.log("  TokenMessenger:    ", address(messenger));
        console.log("  NAVOracle:         ", address(nav));
        console.log("  CCTPRouter:        ", address(router));
        console.log("  USYCParkVault:     ", address(park));
        console.log("  IndexToken:        ", address(index));
        console.log("  RebalanceExecutor: ", address(exec));
    }
}
