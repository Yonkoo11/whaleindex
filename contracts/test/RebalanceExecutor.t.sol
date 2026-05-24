// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test, Vm} from "forge-std/Test.sol";
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

    // Sample 32-byte commitment to an off-chain allocation document.
    bytes32 constant CID = bytes32(uint256(0xC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1DC1D));
    uint16  constant WHALES = 8;

    function setUp() public {
        vm.warp(1_700_000_000);
        usdc = new MockUSDC();
        usyc = new MockUSYC(address(usdc));
        messenger = new MockTokenMessengerV2();
        oracle = new NAVOracle(operator);

        uint32[] memory domains = new uint32[](1);
        domains[0] = 3; // Arbitrum
        router = new CCTPRouter(address(usdc), address(messenger), domains);

        park = new USYCParkVault(address(usdc), address(usyc), address(this));
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

        index.transferOwnership(address(exec));
        park.transferOwnership(address(exec));
        vm.prank(operator);
        oracle.transferOwnership(address(exec));

        usdc.mint(alice, 5_000_000_000);
        vm.prank(alice);
        usdc.approve(address(index), 5_000_000_000);
        vm.prank(alice);
        index.buy(3_000_000_000);
    }

    function _doRebalance(uint256 total, uint256 parkAmt, uint256 newNav, uint64 reportedAt)
        internal returns (uint64 nonce)
    {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        return exec.rebalance(total, parkAmt, 3, recipient, 10, 1000, newNav, reportedAt, CID, WHALES);
    }

    function test_rebalance_routesCCTPAndUpdatesNAV() public {
        uint64 nonce = _doRebalance(200_000_000, 50_000_000, 500_000_000, uint64(block.timestamp));

        assertEq(messenger.callCount(), 1);
        assertEq(nonce, 1);

        (uint256 nav, bool fresh) = oracle.getNAV();
        assertEq(nav, 500_000_000);
        assertTrue(fresh);

        assertEq(park.balanceUSDC(), 50_000_000);
        assertEq(usdc.balanceOf(address(index)), 3_000_000_000 - 200_000_000);
    }

    function test_rebalance_revertsOnSingleMoveExceeded() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.PolicyExceededSingle.selector);
        exec.rebalance(600_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), CID, WHALES);
    }

    function test_rebalance_revertsOnDailyCapExceeded() public {
        _doRebalance(500_000_000, 0, 500_000_000, uint64(block.timestamp));
        vm.warp(block.timestamp + 60);
        _doRebalance(500_000_000, 0, 500_000_000, uint64(block.timestamp));

        vm.warp(block.timestamp + 60);
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.PolicyExceededDaily.selector);
        exec.rebalance(1, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), CID, WHALES);
    }

    function test_rebalance_dailyCapResetsAcrossDays() public {
        _doRebalance(500_000_000, 0, 500_000_000, uint64(block.timestamp));
        _doRebalance(500_000_000, 0, 500_000_000, uint64(block.timestamp + 1));

        vm.warp(block.timestamp + 1 days);

        _doRebalance(500_000_000 - 1, 0, 500_000_000, uint64(block.timestamp));

        assertEq(exec.spentToday(), 500_000_000 - 1);
    }

    function test_rebalance_onlyOwner() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(address(0xBAD));
        vm.expectRevert();
        exec.rebalance(100_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), CID, WHALES);
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

    // --- new behaviour: pause + AllocationDecided + CID validation ---

    function test_rebalance_revertsOnZeroCid() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.MissingAllocationCID.selector);
        exec.rebalance(100_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), bytes32(0), WHALES);
    }

    function test_rebalance_emitsAllocationDecided() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.recordLogs();
        vm.prank(operator);
        exec.rebalance(100_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), CID, WHALES);

        Vm.Log[] memory logs = vm.getRecordedLogs();
        bytes32 sig = keccak256("AllocationDecided(bytes32,uint16,uint64)");
        bool found = false;
        for (uint256 i = 0; i < logs.length; i++) {
            if (logs[i].topics.length > 0 && logs[i].topics[0] == sig) {
                assertEq(logs[i].topics[1], CID);
                found = true;
                break;
            }
        }
        assertTrue(found, "AllocationDecided not emitted");
    }

    function test_pause_blocksRebalance() public {
        vm.prank(operator);
        exec.pause();

        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(); // Pausable: EnforcedPause
        exec.rebalance(100_000_000, 0, 3, recipient, 10, 1000, 500_000_000, uint64(block.timestamp), CID, WHALES);
    }

    function test_unpause_restoresRebalance() public {
        vm.prank(operator);
        exec.pause();
        vm.prank(operator);
        exec.unpause();
        _doRebalance(100_000_000, 0, 500_000_000, uint64(block.timestamp));
    }

    function test_pause_onlyOwner() public {
        vm.prank(address(0xBAD));
        vm.expectRevert();
        exec.pause();
    }
}
