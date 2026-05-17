// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {RebalanceExecutor} from "../src/RebalanceExecutor.sol";
import {IndexToken} from "../src/IndexToken.sol";
import {NAVOracle} from "../src/NAVOracle.sol";
import {CCTPRouter} from "../src/CCTPRouter.sol";
import {USYCParkVault} from "../src/USYCParkVault.sol";
import {MockUSDC} from "../src/mocks/MockUSDC.sol";
import {MockUSYC} from "../src/mocks/MockUSYC.sol";
import {MockTokenMessengerV2} from "../src/mocks/MockTokenMessengerV2.sol";

contract RebalanceExecutorTest is Test {
    MockUSDC usdc;
    MockUSYC usyc;
    MockTokenMessengerV2 messenger;
    NAVOracle oracle;
    IndexToken index;
    CCTPRouter router;
    USYCParkVault park;
    RebalanceExecutor exec;

    address operator = address(0xA1);
    address alice = address(0xA11CE);

    function setUp() public {
        vm.warp(1_700_000_000);
        usdc = new MockUSDC();
        usyc = new MockUSYC(address(usdc));
        messenger = new MockTokenMessengerV2();
        oracle = new NAVOracle(operator);

        uint32[] memory domains = new uint32[](1);
        domains[0] = 3; // Arbitrum
        router = new CCTPRouter(address(usdc), address(messenger), domains);

        // Park vault: temporarily own as test, then transfer to executor.
        park = new USYCParkVault(address(usdc), address(usyc), address(this));

        // Index token: temporarily own as test, then transfer to executor.
        index = new IndexToken(address(usdc), address(oracle), address(this));

        exec = new RebalanceExecutor(
            address(usdc),
            address(index),
            address(oracle),
            address(router),
            address(park),
            operator,
            500_000_000,   // maxSingleMove = 500 USDC
            1_000_000_000  // dailyCap = 1000 USDC
        );

        // Hand over control to executor.
        index.transferOwnership(address(exec));
        park.transferOwnership(address(exec));
        vm.prank(operator);
        oracle.transferOwnership(address(exec));

        usdc.mint(alice, 5_000_000_000);
        vm.prank(alice);
        usdc.approve(address(index), 5_000_000_000);
        vm.prank(alice);
        index.buy(3_000_000_000); // alice deposits 3000 USDC into index, treasury has headroom for multiple rebalances
    }

    function test_rebalance_routesCCTPAndUpdatesNAV() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));

        vm.prank(operator);
        uint64 nonce = exec.rebalance(
            200_000_000,    // total move
            50_000_000,     // park 50
            3,              // Arbitrum
            recipient,
            10,             // maxFee
            1000,           // minFinalityThreshold (1000 = standard finality per CCTP V2)
            500_000_000,    // newNav = 500 USDC (unchanged)
            uint64(block.timestamp)
        );

        // CCTP move was 200 - 50 parked = 150
        assertEq(messenger.callCount(), 1);
        assertEq(nonce, 1);

        // NAV oracle updated and fresh.
        (uint256 nav, bool fresh) = oracle.getNAV();
        assertEq(nav, 500_000_000);
        assertTrue(fresh);

        // USYC park has 50.
        assertEq(park.balanceUSDC(), 50_000_000);

        // Index treasury reduced by 200 (the rebalance pull).
        assertEq(usdc.balanceOf(address(index)), 3_000_000_000 - 200_000_000);
    }

    function test_rebalance_revertsOnSingleMoveExceeded() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.PolicyExceededSingle.selector);
        exec.rebalance(
            600_000_000,    // > 500 maxSingleMove
            0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp)
        );
    }

    function test_rebalance_revertsOnDailyCapExceeded() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));

        // First move uses 500 (the maxSingleMove cap).
        vm.prank(operator);
        exec.rebalance(500_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));

        // Second 500-move would push spentToday to 1000 (still ≤ dailyCap=1000), so OK.
        // But add an extra 1 wei and we breach.
        vm.warp(block.timestamp + 60);
        vm.prank(operator);
        exec.rebalance(500_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));

        // Third move (any size > 0) should breach.
        vm.warp(block.timestamp + 60);
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.PolicyExceededDaily.selector);
        exec.rebalance(1, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));
    }

    function test_rebalance_dailyCapResetsAcrossDays() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));

        vm.prank(operator);
        exec.rebalance(500_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));
        vm.prank(operator);
        exec.rebalance(500_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp + 1));

        // Move to next UTC day.
        vm.warp(block.timestamp + 1 days);

        vm.prank(operator);
        exec.rebalance(500_000_000 - 1, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));

        assertEq(exec.spentToday(), 500_000_000 - 1);
    }

    function test_rebalance_onlyOwner() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(address(0xBAD));
        vm.expectRevert();
        exec.rebalance(100_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp));
    }

    function test_setPolicy_onlyOwner() public {
        vm.prank(operator);
        exec.setPolicy(999, 999);
        (uint256 ms_, uint256 dc) = exec.policy();
        assertEq(ms_, 999);
        assertEq(dc, 999);

        vm.prank(address(0xBAD));
        vm.expectRevert();
        exec.setPolicy(1, 1);
    }
}
