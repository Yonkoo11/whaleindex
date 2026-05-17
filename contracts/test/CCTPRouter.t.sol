// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {CCTPRouter} from "../src/CCTPRouter.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {MockTokenMessengerV2} from "../src/mocks/MockTokenMessengerV2.sol";

contract CCTPRouterTest is Test {
    MockUSDC usdc;
    MockTokenMessengerV2 messenger;
    CCTPRouter router;

    address user = address(0xCAFE);

    function setUp() public {
        usdc = new MockUSDC();
        messenger = new MockTokenMessengerV2();

        uint32[] memory domains = new uint32[](2);
        domains[0] = 3;  // Arbitrum
        domains[1] = 5;  // Solana
        router = new CCTPRouter(address(usdc), address(messenger), domains);

        usdc.mint(user, 1_000_000_000); // 1000 USDC
    }

    function test_routeUSDC_burnsAndEmits() public {
        bytes32 mintRecipient = bytes32(uint256(uint160(user)));

        vm.startPrank(user);
        usdc.approve(address(router), 100_000_000);

        vm.expectEmit(true, true, true, true);
        emit CCTPRouter.Routed(1, 3, mintRecipient, 100_000_000, 50, 1000);

        uint64 nonce = router.routeUSDC(100_000_000, 3, mintRecipient, 50, 1000);
        vm.stopPrank();

        assertEq(nonce, 1);
        assertEq(messenger.callCount(), 1);
        assertEq(usdc.balanceOf(user), 900_000_000);
    }

    function test_routeUSDC_rejectsDisallowedDomain() public {
        vm.startPrank(user);
        usdc.approve(address(router), 100_000_000);

        vm.expectRevert(CCTPRouter.DomainNotAllowed.selector);
        router.routeUSDC(100_000_000, 99, bytes32(uint256(1)), 50, 1000);
        vm.stopPrank();
    }

    function test_routeUSDC_rejectsZeroAmount() public {
        vm.startPrank(user);
        vm.expectRevert(CCTPRouter.ZeroAmount.selector);
        router.routeUSDC(0, 3, bytes32(uint256(1)), 50, 1000);
        vm.stopPrank();
    }

    function test_routeUSDC_rejectsZeroRecipient() public {
        vm.startPrank(user);
        usdc.approve(address(router), 100_000_000);
        vm.expectRevert(CCTPRouter.ZeroRecipient.selector);
        router.routeUSDC(100_000_000, 3, bytes32(0), 50, 1000);
        vm.stopPrank();
    }

    function test_setDomainAllowed_onlyOwner() public {
        vm.prank(address(0xBAD));
        vm.expectRevert();
        router.setDomainAllowed(7, true);

        router.setDomainAllowed(7, true); // owner = test contract
        assertTrue(router.allowedDomain(7));
    }
}
