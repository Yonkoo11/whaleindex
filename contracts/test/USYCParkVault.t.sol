// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {USYCParkVault} from "../src/USYCParkVault.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {MockUSYC} from "../src/mocks/MockUSYC.sol";

contract USYCParkVaultTest is Test {
    MockUSDC usdc;
    MockUSYC usyc;
    USYCParkVault park;
    address executor = address(0xE1);

    function setUp() public {
        usdc = new MockUSDC();
        usyc = new MockUSYC(address(usdc));
        park = new USYCParkVault(address(usdc), address(usyc), executor);

        usdc.mint(executor, 1_000_000_000);
    }

    function test_park_pullsUSDCAndMintsShares() public {
        vm.startPrank(executor);
        usdc.approve(address(park), 100_000_000);
        uint256 shares = park.park(100_000_000);
        vm.stopPrank();

        assertEq(shares, 100_000_000);
        assertEq(park.balanceUSDC(), 100_000_000);
        assertEq(usdc.balanceOf(executor), 900_000_000);
    }

    function test_unpark_returnsUSDC() public {
        vm.startPrank(executor);
        usdc.approve(address(park), 100_000_000);
        park.park(100_000_000);

        uint256 returned = park.unpark(60_000_000);
        vm.stopPrank();

        assertEq(returned, 60_000_000);
        assertEq(usdc.balanceOf(executor), 960_000_000);
        assertEq(park.balanceUSDC(), 40_000_000);
    }

    function test_park_onlyOwner() public {
        vm.prank(address(0xBAD));
        vm.expectRevert();
        park.park(100);
    }
}
