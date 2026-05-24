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

    // --- off-chain CCTP path: prepareRebalance + commitRebalance ---

    function _prepare(uint256 total, uint256 parkAmt) internal returns (uint256 burnId) {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        return exec.prepareRebalance(
            total, parkAmt, 3, recipient, 50_000, 2000, CID, WHALES
        );
    }

    function test_prepareRebalance_transfersToOperatorAndEmits() public {
        uint256 opBefore = usdc.balanceOf(operator);
        uint256 burnId = _prepare(200_000_000, 50_000_000);
        assertEq(burnId, 1);

        // Operator received the routing amount (200 - 50 parked = 150).
        assertEq(usdc.balanceOf(operator) - opBefore, 150_000_000);

        // Park got the parked amount.
        assertEq(park.balanceUSDC(), 50_000_000);

        // No NAV update yet — that's commitRebalance's job.
        (uint256 nav,) = oracle.getNAV();
        assertEq(nav, 0);

        // PreparedBurn stored.
        (uint256 amount, uint32 dest, bytes32 recip, uint256 fee, uint32 fin, bytes32 cid, bool committed) =
            exec.preparedBurns(burnId);
        assertEq(amount, 150_000_000);
        assertEq(dest, uint32(3));
        assertEq(recip, bytes32(uint256(uint160(address(0xDEAD)))));
        assertEq(fee, 50_000);
        assertEq(fin, uint32(2000));
        assertEq(cid, CID);
        assertFalse(committed);
    }

    function test_prepareRebalance_revertsOnZeroCid() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.MissingAllocationCID.selector);
        exec.prepareRebalance(100_000_000, 0, 3, recipient, 50_000, 2000, bytes32(0), WHALES);
    }

    function test_prepareRebalance_enforcesPolicy() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.PolicyExceededSingle.selector);
        exec.prepareRebalance(600_000_000, 0, 3, recipient, 50_000, 2000, CID, WHALES);
    }

    function test_commitRebalance_updatesNAV() public {
        uint256 burnId = _prepare(200_000_000, 0);
        vm.prank(operator);
        exec.commitRebalance(burnId, 12345, 500_000_000, uint64(block.timestamp));

        (uint256 nav, bool fresh) = oracle.getNAV();
        assertEq(nav, 500_000_000);
        assertTrue(fresh);

        // Marked committed.
        (, , , , , , bool committed) = exec.preparedBurns(burnId);
        assertTrue(committed);
    }

    function test_commitRebalance_revertsOnUnknownBurnId() public {
        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.UnknownBurnId.selector);
        exec.commitRebalance(999, 1, 500_000_000, uint64(block.timestamp));
    }

    function test_commitRebalance_revertsOnDoubleCommit() public {
        uint256 burnId = _prepare(100_000_000, 0);
        vm.prank(operator);
        exec.commitRebalance(burnId, 1, 100_000_000, uint64(block.timestamp));

        vm.prank(operator);
        vm.expectRevert(RebalanceExecutor.AlreadyCommitted.selector);
        exec.commitRebalance(burnId, 2, 200_000_000, uint64(block.timestamp + 1));
    }

    function test_pause_blocksPrepareAndCommit() public {
        vm.prank(operator);
        exec.pause();

        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.prank(operator);
        vm.expectRevert();
        exec.prepareRebalance(100_000_000, 0, 3, recipient, 50_000, 2000, CID, WHALES);

        // Even commit is paused — operator must unpause first.
        vm.prank(operator);
        vm.expectRevert();
        exec.commitRebalance(1, 1, 1, uint64(block.timestamp));
    }

    function test_prepareRebalance_emitsBurnPreparedWithExpectedArgs() public {
        bytes32 recipient = bytes32(uint256(uint160(address(0xDEAD))));
        vm.recordLogs();
        vm.prank(operator);
        exec.prepareRebalance(100_000_000, 0, 3, recipient, 50_000, 2000, CID, WHALES);

        Vm.Log[] memory logs = vm.getRecordedLogs();
        bytes32 sig = keccak256("BurnPrepared(uint256,address,uint256,uint32,bytes32,uint256,uint32,bytes32)");
        bool found = false;
        for (uint256 i = 0; i < logs.length; i++) {
            if (logs[i].topics.length > 0 && logs[i].topics[0] == sig) {
                // burnId is indexed
                assertEq(uint256(logs[i].topics[1]), 1);
                // operator is indexed
                assertEq(address(uint160(uint256(logs[i].topics[2]))), operator);
                found = true;
                break;
            }
        }
        assertTrue(found, "BurnPrepared not emitted");
    }

    function test_nextBurnId_increments() public {
        assertEq(exec.nextBurnId(), 0);
        _prepare(100_000_000, 0);
        assertEq(exec.nextBurnId(), 1);
        _prepare(100_000_000, 0);
        assertEq(exec.nextBurnId(), 2);
    }
}
