// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {IndexToken} from "../src/IndexToken.sol";
import {NAVOracle} from "../src/NAVOracle.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";

contract IndexTokenTest is Test {
    MockUSDC usdc;
    NAVOracle oracle;
    IndexToken index;

    address operator = address(0xA1);
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        vm.warp(1_700_000_000);
        usdc = new MockUSDC();
        oracle = new NAVOracle(operator);
        index = new IndexToken(address(usdc), address(oracle), address(this));

        usdc.mint(alice, 1_000_000_000); // 1000 USDC
        usdc.mint(bob,   1_000_000_000);
    }

    function test_firstBuy_mintsAtOneToOneScaled() public {
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        uint256 shares = index.buy(100_000_000);
        vm.stopPrank();

        assertEq(shares, 100_000_000 * 1e12); // SHARE_SCALE
        assertEq(index.totalSupply(), 100_000_000 * 1e12);
        assertEq(index.balanceOf(alice), 100_000_000 * 1e12);
    }

    function test_secondBuy_followsNAV() public {
        // Alice buys at first-mint price.
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        index.buy(100_000_000);
        vm.stopPrank();

        // Operator publishes NAV = 200 USDC (i.e. positions doubled in value).
        vm.prank(operator);
        oracle.updateNAV(200_000_000, uint64(block.timestamp));

        // Bob buys 50 USDC worth. shares = supply * 50 / nav = supply / 4
        vm.startPrank(bob);
        usdc.approve(address(index), 50_000_000);
        uint256 shares = index.buy(50_000_000);
        vm.stopPrank();

        assertEq(shares, (100_000_000 * 1e12 * 50_000_000) / 200_000_000);
    }

    function test_redeem_returnsProRata() public {
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        index.buy(100_000_000);
        vm.stopPrank();

        // NAV stays equal to deposit; redeem half.
        vm.prank(operator);
        oracle.updateNAV(100_000_000, uint64(block.timestamp));

        vm.prank(alice);
        uint256 out = index.redeem(50_000_000 * 1e12); // half the shares

        assertEq(out, 50_000_000);
        assertEq(usdc.balanceOf(alice), 950_000_000);
    }

    function test_buy_revertsOnStaleNAV() public {
        // First buy primes the pool with 1:1 mint.
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        index.buy(100_000_000);
        vm.stopPrank();

        // Operator publishes a NAV then we warp past the freshness window.
        vm.prank(operator);
        oracle.updateNAV(100_000_000, uint64(block.timestamp));

        vm.warp(block.timestamp + 120); // 120s > 60s window

        vm.startPrank(bob);
        usdc.approve(address(index), 50_000_000);
        vm.expectRevert(IndexToken.StaleNAV.selector);
        index.buy(50_000_000);
        vm.stopPrank();
    }

    function test_redeem_revertsOnStaleNAV() public {
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        index.buy(100_000_000);
        vm.stopPrank();

        vm.prank(operator);
        oracle.updateNAV(100_000_000, uint64(block.timestamp));
        vm.warp(block.timestamp + 120);

        vm.prank(alice);
        vm.expectRevert(IndexToken.StaleNAV.selector);
        index.redeem(50_000_000 * 1e12);
    }

    function test_withdrawForRebalance_onlyOwner() public {
        vm.startPrank(alice);
        usdc.approve(address(index), 100_000_000);
        index.buy(100_000_000);
        vm.stopPrank();

        vm.prank(address(0xBAD));
        vm.expectRevert();
        index.withdrawForRebalance(address(0xBAD), 1);

        index.withdrawForRebalance(address(0xBEEF), 10_000_000); // test contract = owner
        assertEq(usdc.balanceOf(address(0xBEEF)), 10_000_000);
    }

    function test_sharePrice_initial() public view {
        assertEq(index.sharePrice(), 1e6);
    }
}
