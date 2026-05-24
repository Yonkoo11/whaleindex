// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {WhaleAttestation} from "../src/v3/WhaleAttestation.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

contract WhaleAttestationTest is Test {
    MockUSDC usdc;
    WhaleAttestation att;

    address operator = address(0xA1);
    address whale1   = address(0xBEE1);
    address whale2   = address(0xBEE2);
    address beneficiary = address(0xCAFE);

    bytes32 constant EVIDENCE_CID = bytes32(uint256(0xDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0DEDEC0));

    function setUp() public {
        vm.warp(1_700_000_000);
        usdc = new MockUSDC();
        att = new WhaleAttestation(
            address(usdc),
            beneficiary,
            5000,         // maxSlashBps = 50%
            7 days,       // unbondCooldown
            operator
        );

        usdc.mint(whale1, 10_000_000_000); // 10K USDC
        usdc.mint(whale2, 10_000_000_000);
    }

    // --- registration ---

    function test_bond_revertsWhenNotRegistered() public {
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        vm.expectRevert(WhaleAttestation.NotRegistered.selector);
        att.bond(100_000_000);
        vm.stopPrank();
    }

    function test_setRegisteredWhale_onlyOwner() public {
        vm.prank(address(0xBAD));
        vm.expectRevert();
        att.setRegisteredWhale(whale1, true);

        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        (, , , bool reg) = att.attestations(whale1);
        assertTrue(reg);
    }

    // --- bond ---

    function test_bond_acceptsAndAccumulates() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);

        vm.startPrank(whale1);
        usdc.approve(address(att), 500_000_000);
        att.bond(100_000_000);
        att.bond(200_000_000);
        vm.stopPrank();

        assertEq(att.bondAmount(whale1), 300_000_000);
        assertTrue(att.isBonded(whale1));
    }

    function test_bond_revertsOnZero() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.prank(whale1);
        vm.expectRevert(WhaleAttestation.BondTooSmall.selector);
        att.bond(0);
    }

    function test_bond_cancelsPendingUnbondRequest() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);

        vm.startPrank(whale1);
        usdc.approve(address(att), 500_000_000);
        att.bond(100_000_000);
        att.requestUnbond();
        (, , uint64 reqAt1, ) = att.attestations(whale1);
        assertGt(reqAt1, 0);

        // Top-up cancels the unbond request.
        att.bond(50_000_000);
        (, , uint64 reqAt2, ) = att.attestations(whale1);
        assertEq(reqAt2, 0);
        vm.stopPrank();
    }

    // --- slash ---

    function test_slash_movesUsdcToBeneficiary() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 1_000_000_000);
        att.bond(1_000_000_000);
        vm.stopPrank();

        uint256 benBefore = usdc.balanceOf(beneficiary);
        vm.prank(operator);
        att.slash(whale1, 2000, EVIDENCE_CID); // 20% slash

        // 20% of 1000 USDC = 200 USDC
        assertEq(usdc.balanceOf(beneficiary) - benBefore, 200_000_000);
        assertEq(att.bondAmount(whale1), 800_000_000);
    }

    function test_slash_revertsAboveMaxSlashBps() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.stopPrank();

        vm.prank(operator);
        vm.expectRevert(WhaleAttestation.SlashTooLarge.selector);
        att.slash(whale1, 5001, EVIDENCE_CID); // 50.01% > 50% cap
    }

    function test_slash_revertsOnZeroBps() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.stopPrank();

        vm.prank(operator);
        vm.expectRevert(WhaleAttestation.SlashTooLarge.selector);
        att.slash(whale1, 0, EVIDENCE_CID);
    }

    function test_slash_revertsOnZeroCid() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.stopPrank();

        vm.prank(operator);
        vm.expectRevert(WhaleAttestation.MissingEvidenceCID.selector);
        att.slash(whale1, 2000, bytes32(0));
    }

    function test_slash_revertsWithoutBond() public {
        vm.prank(operator);
        vm.expectRevert(WhaleAttestation.NoBond.selector);
        att.slash(whale1, 1000, EVIDENCE_CID);
    }

    function test_slash_onlyOwner() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.stopPrank();

        vm.prank(address(0xBAD));
        vm.expectRevert();
        att.slash(whale1, 1000, EVIDENCE_CID);
    }

    // --- unbond flow ---

    function test_unbondFlow_succeedsAfterCooldown() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 500_000_000);
        att.bond(500_000_000);
        att.requestUnbond();
        vm.stopPrank();

        vm.expectRevert(WhaleAttestation.CooldownNotElapsed.selector);
        vm.prank(whale1);
        att.claimUnbond();

        vm.warp(block.timestamp + 7 days + 1);
        uint256 before = usdc.balanceOf(whale1);
        vm.prank(whale1);
        att.claimUnbond();
        assertEq(usdc.balanceOf(whale1) - before, 500_000_000);
        assertEq(att.bondAmount(whale1), 0);
        assertFalse(att.isBonded(whale1));
    }

    function test_requestUnbond_revertsIfAlreadyRequested() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        att.requestUnbond();
        vm.expectRevert(WhaleAttestation.AlreadyRequested.selector);
        att.requestUnbond();
        vm.stopPrank();
    }

    function test_slashable_during_cooldown() public {
        // Whale can't escape decay by front-running an unbond request.
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 1_000_000_000);
        att.bond(1_000_000_000);
        att.requestUnbond();
        vm.stopPrank();

        // Mid-cooldown, operator can still slash.
        vm.warp(block.timestamp + 3 days);
        vm.prank(operator);
        att.slash(whale1, 3000, EVIDENCE_CID); // 30% slash
        assertEq(att.bondAmount(whale1), 700_000_000);

        // After cooldown completes, whale gets the remainder (700).
        vm.warp(block.timestamp + 5 days);
        uint256 before = usdc.balanceOf(whale1);
        vm.prank(whale1);
        att.claimUnbond();
        assertEq(usdc.balanceOf(whale1) - before, 700_000_000);
    }

    function test_claimUnbond_revertsWithoutRequest() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.expectRevert(WhaleAttestation.NoUnbondRequest.selector);
        att.claimUnbond();
        vm.stopPrank();
    }

    // --- views + admin ---

    function test_unbondEligibleAt_returnsZeroWithoutRequest() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        att.bond(100_000_000);
        vm.stopPrank();
        assertEq(att.unbondEligibleAt(whale1), 0);
    }

    function test_setMaxSlashBps_onlyOwner() public {
        vm.prank(operator);
        att.setMaxSlashBps(7500);
        assertEq(att.maxSlashBps(), 7500);

        vm.prank(address(0xBAD));
        vm.expectRevert();
        att.setMaxSlashBps(1000);
    }

    function test_setMaxSlashBps_rejectsZero() public {
        vm.prank(operator);
        vm.expectRevert(WhaleAttestation.InvalidBps.selector);
        att.setMaxSlashBps(0);
    }

    function test_pause_blocksBondAndSlash() public {
        vm.prank(operator);
        att.setRegisteredWhale(whale1, true);
        vm.prank(operator);
        att.pause();

        vm.startPrank(whale1);
        usdc.approve(address(att), 100_000_000);
        vm.expectRevert();
        att.bond(100_000_000);
        vm.stopPrank();

        vm.prank(operator);
        vm.expectRevert();
        att.slash(whale1, 1000, EVIDENCE_CID);
    }

    function test_constructor_revertsOnZeroAddress() public {
        vm.expectRevert(WhaleAttestation.ZeroAddress.selector);
        new WhaleAttestation(address(0), beneficiary, 5000, 7 days, operator);
    }

    function test_constructor_revertsOnInvalidBps() public {
        vm.expectRevert(WhaleAttestation.InvalidBps.selector);
        new WhaleAttestation(address(usdc), beneficiary, 0, 7 days, operator);
    }
}
