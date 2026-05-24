// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {WhaleAttestation} from "../src/v3/WhaleAttestation.sol";

/// Deploys WhaleAttestation V3 standalone, pointing at the already-deployed
/// V2 IndexToken as the slash beneficiary (slashes lift NAV for survivors).
///
/// Env vars:
///   DEPLOYER_PRIVATE_KEY   (required, signs the deploy)
///   USDC_ADDRESS           (defaults to 0x3600... real native USDC on Arc)
///   SLASH_BENEFICIARY      (defaults to V2 IndexToken: 0x68a8809E...)
///   MAX_SLASH_BPS          (defaults to 5000 = 50%)
///   UNBOND_COOLDOWN_SECS   (defaults to 604800 = 7 days)
///   OPERATOR_ADDRESS       (defaults to deployer)
contract DeployWhaleAttestationScript is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer    = vm.addr(deployerKey);

        address usdc        = vm.envOr("USDC_ADDRESS", address(0x3600000000000000000000000000000000000000));
        // Default to the V3 IndexToken (current live deploy at addresses.IndexToken).
        // V2 default kept in repo history under v2_legacy_addresses_for_reference.
        address beneficiary = vm.envOr("SLASH_BENEFICIARY", address(0xAdEa3FaE6011c2D275868d1c1933B37BE7648269));
        uint256 maxSlashBps = vm.envOr("MAX_SLASH_BPS", uint256(5000));
        uint64  cooldown    = uint64(vm.envOr("UNBOND_COOLDOWN_SECS", uint256(7 days)));
        address operator    = vm.envOr("OPERATOR_ADDRESS", deployer);

        vm.startBroadcast(deployerKey);
        WhaleAttestation att = new WhaleAttestation(usdc, beneficiary, maxSlashBps, cooldown, operator);
        vm.stopBroadcast();

        console.log("WhaleAttestation deployed:");
        console.log("  address:        ", address(att));
        console.log("  usdc:           ", usdc);
        console.log("  beneficiary:    ", beneficiary);
        console.log("  maxSlashBps:    ", maxSlashBps);
        console.log("  unbondCooldown: ", uint256(cooldown));
        console.log("  operator:       ", operator);
    }
}
