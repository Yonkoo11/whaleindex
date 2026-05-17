// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {ITokenMessengerV2} from "../interfaces/ICircleCCTPv2.sol";

/// Mock for CCTP V2 TokenMessenger. Records calls and burns the USDC.
contract MockTokenMessengerV2 is ITokenMessengerV2 {
    struct Call {
        uint256 amount;
        uint32  destinationDomain;
        bytes32 mintRecipient;
        address burnToken;
        bytes32 destinationCaller;
        uint256 maxFee;
        uint32  minFinalityThreshold;
        uint64  nonce;
    }

    Call[] public calls;
    uint64 public nextNonce = 1;

    function depositForBurn(
        uint256 amount,
        uint32 destinationDomain,
        bytes32 mintRecipient,
        address burnToken,
        bytes32 destinationCaller,
        uint256 maxFee,
        uint32 minFinalityThreshold
    ) external override returns (uint64 nonce) {
        // Simulate a real CCTP V2 burn: pull tokens, burn them by sending to address(0).
        IERC20(burnToken).transferFrom(msg.sender, address(this), amount);

        nonce = nextNonce++;
        calls.push(Call({
            amount: amount,
            destinationDomain: destinationDomain,
            mintRecipient: mintRecipient,
            burnToken: burnToken,
            destinationCaller: destinationCaller,
            maxFee: maxFee,
            minFinalityThreshold: minFinalityThreshold,
            nonce: nonce
        }));
    }

    function callCount() external view returns (uint256) { return calls.length; }
}
