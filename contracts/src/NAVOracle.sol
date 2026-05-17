// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

/// @title NAVOracle — operator-signed NAV with freshness window.
/// V1: owner-only updates with a configurable freshness window (default 60s).
/// V2: swap in Pyth EVM pull oracle when Arc supports it.
/// Readers MUST check `isFresh()` before trusting `getNAV()`.
contract NAVOracle is Ownable {
    uint256 public nav;            // NAV in USDC base units (6 decimals)
    uint64  public updatedAt;      // unix seconds
    uint64  public freshnessWindow;// seconds a NAV reading is considered fresh

    event NAVUpdated(uint256 nav, uint64 timestamp);
    event FreshnessWindowChanged(uint64 oldWindow, uint64 newWindow);

    error StaleUpdate();
    error ZeroNAV();

    constructor(address operator) Ownable(operator) {
        freshnessWindow = 60;
    }

    function updateNAV(uint256 newNav, uint64 reportedAt) external onlyOwner {
        if (newNav == 0) revert ZeroNAV();
        // Reject backdated updates to prevent a stuck old update from being re-broadcast.
        if (reportedAt < updatedAt) revert StaleUpdate();
        nav = newNav;
        updatedAt = reportedAt;
        emit NAVUpdated(newNav, reportedAt);
    }

    function setFreshnessWindow(uint64 newWindow) external onlyOwner {
        emit FreshnessWindowChanged(freshnessWindow, newWindow);
        freshnessWindow = newWindow;
    }

    function isFresh() public view returns (bool) {
        if (updatedAt == 0) return false;
        return block.timestamp <= uint256(updatedAt) + uint256(freshnessWindow);
    }

    function getNAV() external view returns (uint256 navOut, bool fresh) {
        return (nav, isFresh());
    }
}
