// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

/// @title NAVOracle — operator-signed NAV with freshness window and per-update delta bound.
/// V1: owner-only updates with a configurable freshness window (default 60s) and a
/// maximum allowed per-update relative change (default 5000bps = 50%).
/// V2: swap in Pyth EVM pull oracle when Arc supports it.
/// Readers MUST check `isFresh()` before trusting `getNAV()`.
contract NAVOracle is Ownable {
    uint256 public constant BPS_DENOMINATOR = 10_000;

    uint256 public nav;             // NAV in USDC base units (6 decimals)
    uint64  public updatedAt;       // unix seconds
    uint64  public freshnessWindow; // seconds a NAV reading is considered fresh
    uint256 public maxDeltaBps;     // bps cap on |newNav - nav| / nav per update

    event NAVUpdated(uint256 nav, uint64 timestamp);
    event FreshnessWindowChanged(uint64 oldWindow, uint64 newWindow);
    event MaxDeltaBpsChanged(uint256 oldBps, uint256 newBps);

    error StaleUpdate();
    error ZeroNAV();
    error NAVDeltaExceeded(uint256 oldNav, uint256 newNav, uint256 maxDeltaBps);
    error InvalidBps();

    constructor(address operator) Ownable(operator) {
        freshnessWindow = 60;
        maxDeltaBps = 5_000; // 50% default
    }

    function updateNAV(uint256 newNav, uint64 reportedAt) external onlyOwner {
        if (newNav == 0) revert ZeroNAV();
        if (reportedAt < updatedAt) revert StaleUpdate();

        // First update has no prior reference — bound check skipped.
        if (nav > 0) {
            uint256 delta = newNav > nav ? newNav - nav : nav - newNav;
            // delta / nav <= maxDeltaBps / BPS_DENOMINATOR  iff  delta * BPS_DENOMINATOR <= nav * maxDeltaBps
            if (delta * BPS_DENOMINATOR > nav * maxDeltaBps) {
                revert NAVDeltaExceeded(nav, newNav, maxDeltaBps);
            }
        }

        nav = newNav;
        updatedAt = reportedAt;
        emit NAVUpdated(newNav, reportedAt);
    }

    function setFreshnessWindow(uint64 newWindow) external onlyOwner {
        emit FreshnessWindowChanged(freshnessWindow, newWindow);
        freshnessWindow = newWindow;
    }

    function setMaxDeltaBps(uint256 newBps) external onlyOwner {
        if (newBps == 0 || newBps > BPS_DENOMINATOR * 10) revert InvalidBps(); // sane cap: <=1000% per update
        emit MaxDeltaBpsChanged(maxDeltaBps, newBps);
        maxDeltaBps = newBps;
    }

    function isFresh() public view returns (bool) {
        if (updatedAt == 0) return false;
        return block.timestamp <= uint256(updatedAt) + uint256(freshnessWindow);
    }

    function getNAV() external view returns (uint256 navOut, bool fresh) {
        return (nav, isFresh());
    }
}
