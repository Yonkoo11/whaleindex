// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// CCTP V2 TokenMessenger (verified shape from Circle docs, 2026-05-17).
// V2 added maxFee + minFinalityThreshold for fast-transfers vs standard finality.
interface ITokenMessengerV2 {
    function depositForBurn(
        uint256 amount,
        uint32 destinationDomain,
        bytes32 mintRecipient,
        address burnToken,
        bytes32 destinationCaller,
        uint256 maxFee,
        uint32 minFinalityThreshold
    ) external returns (uint64 nonce);
}
