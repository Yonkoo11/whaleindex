// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {NAVOracle} from "../src/NAVOracle.sol";

contract NAVOracleTest is Test {
    NAVOracle oracle;
    address operator = address(0xA1);

    function setUp() public {
        oracle = new NAVOracle(operator);
    }

    function test_initialState() public view {
        assertEq(oracle.nav(), 0);
        assertEq(oracle.updatedAt(), 0);
        assertEq(oracle.freshnessWindow(), 60);
        assertFalse(oracle.isFresh()); // not fresh because never updated
    }

    function test_updateNAV_setsValuesAndEmits() public {
        vm.warp(1_700_000_000);
        vm.prank(operator);
        vm.expectEmit(true, true, true, true);
        emit NAVOracle.NAVUpdated(100_000_000, uint64(block.timestamp));
        oracle.updateNAV(100_000_000, uint64(block.timestamp));

        assertEq(oracle.nav(), 100_000_000);
        assertEq(oracle.updatedAt(), uint64(block.timestamp));
        assertTrue(oracle.isFresh());
    }

    function test_updateNAV_revertOnZero() public {
        vm.prank(operator);
        vm.expectRevert(NAVOracle.ZeroNAV.selector);
        oracle.updateNAV(0, uint64(block.timestamp));
    }

    function test_updateNAV_revertOnBackdated() public {
        vm.warp(1_700_000_000);
        vm.prank(operator);
        oracle.updateNAV(100_000_000, uint64(block.timestamp));

        vm.prank(operator);
        vm.expectRevert(NAVOracle.StaleUpdate.selector);
        oracle.updateNAV(100_000_000, uint64(block.timestamp) - 10);
    }

    function test_isFresh_followsWindow() public {
        vm.warp(1_700_000_000);
        vm.prank(operator);
        oracle.updateNAV(100, uint64(block.timestamp));
        assertTrue(oracle.isFresh());

        vm.warp(block.timestamp + 59);
        assertTrue(oracle.isFresh());

        vm.warp(block.timestamp + 2); // now 61s after update
        assertFalse(oracle.isFresh());
    }

    function test_setFreshnessWindow_onlyOwner() public {
        vm.prank(operator);
        oracle.setFreshnessWindow(300);
        assertEq(oracle.freshnessWindow(), 300);

        vm.prank(address(0xBAD));
        vm.expectRevert();
        oracle.setFreshnessWindow(120);
    }

    function test_updateNAV_onlyOwner() public {
        vm.prank(address(0xBAD));
        vm.expectRevert();
        oracle.updateNAV(100, uint64(block.timestamp));
    }
}
