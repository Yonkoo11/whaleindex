// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {Pausable} from "openzeppelin-contracts/contracts/utils/Pausable.sol";
import {IndexToken} from "./IndexToken.sol";
import {NAVOracle} from "./NAVOracle.sol";
import {CCTPRouter} from "./CCTPRouter.sol";
import {USYCParkVault} from "./USYCParkVault.sol";

/// @title RebalanceExecutor — the only contract authorised to move protocol USDC.
/// Enforces a Wallets-SDK-style on-chain policy: per-move cap, daily cap, destination allowlist.
/// Emits AllocationDecided(cid) so the off-chain allocation decision (whale list + weights,
/// pinned to IPFS) is anchored to every on-chain rebalance.
/// V1 ownership = single operator agent. V2 = 2/3 multisig.
contract RebalanceExecutor is Ownable, Pausable {
    using SafeERC20 for IERC20;

    IERC20         public immutable usdc;
    IndexToken     public immutable index;
    NAVOracle      public immutable navOracle;
    CCTPRouter     public immutable router;
    USYCParkVault  public immutable park;

    /// Policy struct mirrors Circle Wallets SDK spending-policy concept.
    struct Policy {
        uint256 maxSingleMove;  // USDC base units
        uint256 dailyCap;       // USDC base units, rolling on UTC day boundary
    }
    Policy public policy;

    /// Bookkeeping for daily-cap enforcement.
    uint256 public dayBucket;       // block.timestamp / 1 days at last update
    uint256 public spentToday;      // USDC moved cross-chain today

    event PolicyChanged(uint256 maxSingleMove, uint256 dailyCap);
    event RebalanceExecuted(
        uint32  indexed destinationDomain,
        bytes32 indexed mintRecipient,
        uint256 usdcOut,
        uint256 navAfter,
        uint64  reportedAt
    );
    /// Anchors the off-chain allocation decision to this on-chain rebalance.
    /// cid is a 32-byte commitment (IPFS CIDv1 truncated, or keccak256 of the doc)
    /// to a public JSON document containing the whale list + per-whale weights + reasoning.
    event AllocationDecided(
        bytes32 indexed cid,
        uint16  whaleCount,
        uint64  reportedAt
    );

    error PolicyExceededSingle();
    error PolicyExceededDaily();
    error MissingAllocationCID();

    constructor(
        address usdc_,
        address index_,
        address navOracle_,
        address router_,
        address park_,
        address operator,
        uint256 maxSingleMove_,
        uint256 dailyCap_
    ) Ownable(operator) {
        usdc      = IERC20(usdc_);
        index     = IndexToken(index_);
        navOracle = NAVOracle(navOracle_);
        router    = CCTPRouter(router_);
        park      = USYCParkVault(park_);
        policy    = Policy({maxSingleMove: maxSingleMove_, dailyCap: dailyCap_});
    }

    function setPolicy(uint256 maxSingleMove_, uint256 dailyCap_) external onlyOwner {
        policy = Policy({maxSingleMove: maxSingleMove_, dailyCap: dailyCap_});
        emit PolicyChanged(maxSingleMove_, dailyCap_);
    }

    /// Owner-only emergency stop. Pauses rebalance(); existing index pause/unpause
    /// is independent so buyers can still redeem while the agent is halted.
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    /// Core rebalance: pull USDC from index → route via CCTP V2 → update NAV oracle.
    /// `parkAmount` parameter optionally diverts a portion to USYC before routing.
    /// `allocationCid` is a non-zero 32-byte commitment to the off-chain allocation
    /// document (whale list + weights + reasoning). The emitted AllocationDecided
    /// event lets indexers tie every on-chain move back to the agent's decision.
    function rebalance(
        uint256 totalUsdcAmount,
        uint256 parkAmount,
        uint32  destinationDomain,
        bytes32 mintRecipient,
        uint256 maxFee,
        uint32  minFinalityThreshold,
        uint256 newNav,
        uint64  reportedAt,
        bytes32 allocationCid,
        uint16  whaleCount
    ) external onlyOwner whenNotPaused returns (uint64 cctpNonce) {
        if (allocationCid == bytes32(0)) revert MissingAllocationCID();
        emit AllocationDecided(allocationCid, whaleCount, reportedAt);

        _checkAndAccrue(totalUsdcAmount);

        // Pull USDC from index treasury into this executor.
        index.withdrawForRebalance(address(this), totalUsdcAmount);

        // Park residual idle USDC in USYC for yield.
        if (parkAmount > 0) {
            usdc.forceApprove(address(park), parkAmount);
            park.park(parkAmount);
        }

        // Route the remaining USDC via CCTP V2.
        uint256 routeAmount = totalUsdcAmount - parkAmount;
        if (routeAmount > 0) {
            usdc.forceApprove(address(router), routeAmount);
            cctpNonce = router.routeUSDC(
                routeAmount,
                destinationDomain,
                mintRecipient,
                maxFee,
                minFinalityThreshold
            );
        }

        // Update NAV to reflect post-rebalance state.
        navOracle.updateNAV(newNav, reportedAt);

        emit RebalanceExecuted(destinationDomain, mintRecipient, totalUsdcAmount, newNav, reportedAt);
    }

    function _checkAndAccrue(uint256 amount) internal {
        if (amount > policy.maxSingleMove) revert PolicyExceededSingle();

        uint256 today = block.timestamp / 1 days;
        if (today != dayBucket) {
            dayBucket = today;
            spentToday = 0;
        }
        uint256 newSpent = spentToday + amount;
        if (newSpent > policy.dailyCap) revert PolicyExceededDaily();
        spentToday = newSpent;
    }
}
