// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {ITokenMessengerV2} from "../interfaces/ICircleCCTPv2.sol";

/// Minimal probe — isolates whether a contract on Arc can burn USDC via CCTP V2.
/// If this works, our CCTPRouter has a bug. If this fails, contract-side CCTP on Arc
/// has an undocumented gotcha (msg.sender restriction, etc).
contract CCTPProbe {
    /// Isolates: can a contract on Arc set an ERC20 allowance on native USDC?
    function justApprove(address usdc, address spender, uint256 amount) external {
        IERC20(usdc).approve(spender, amount);
    }

    /// Isolates: can a contract on Arc call depositForBurn after the approval is set?
    /// Caller must pre-fund this contract with USDC and pre-set its approval to the messenger.
    function justBurn(
        uint256 amount,
        uint32 destinationDomain,
        bytes32 mintRecipient,
        address usdc,
        address messenger,
        uint256 maxFee,
        uint32 minFinalityThreshold
    ) external returns (uint64) {
        return ITokenMessengerV2(messenger).depositForBurn(
            amount, destinationDomain, mintRecipient, usdc, bytes32(0), maxFee, minFinalityThreshold
        );
    }

    function probe(
        uint256 amount,
        uint32 destinationDomain,
        bytes32 mintRecipient,
        address usdc,
        address messenger,
        uint256 maxFee,
        uint32 minFinalityThreshold
    ) external returns (uint64 nonce) {
        IERC20(usdc).transferFrom(msg.sender, address(this), amount);
        IERC20(usdc).approve(messenger, amount);
        return ITokenMessengerV2(messenger).depositForBurn(
            amount,
            destinationDomain,
            mintRecipient,
            usdc,
            bytes32(0),
            maxFee,
            minFinalityThreshold
        );
    }
}
