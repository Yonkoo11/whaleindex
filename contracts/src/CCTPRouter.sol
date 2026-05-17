// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {ITokenMessengerV2} from "./interfaces/ICircleCCTPv2.sol";

/// @title CCTPRouter — wraps Circle CCTP V2 TokenMessenger for venue settlement.
/// The router is the only place USDC can leave the protocol; routing rules live here.
contract CCTPRouter is Ownable {
    using SafeERC20 for IERC20;

    IERC20 public immutable usdc;
    ITokenMessengerV2 public immutable tokenMessenger;

    /// Allowlist of destination domains (CCTP V2 numeric IDs) the router will route to.
    /// Set at construction; new venues require owner update.
    /// Verified domains as of 2026-05-17:
    ///   0 = Ethereum, 1 = Avalanche, 2 = OP, 3 = Arbitrum, 5 = Solana,
    ///   6 = Base, 7 = Polygon PoS, 10 = Unichain
    mapping(uint32 => bool) public allowedDomain;

    event Routed(
        uint64  indexed nonce,
        uint32  indexed destinationDomain,
        bytes32 mintRecipient,
        uint256 amount,
        uint256 maxFee,
        uint32  minFinalityThreshold
    );

    event DomainAllowlistChanged(uint32 indexed domain, bool allowed);

    error DomainNotAllowed();
    error ZeroAmount();
    error ZeroRecipient();

    constructor(address usdc_, address tokenMessenger_, uint32[] memory initialDomains) Ownable(msg.sender) {
        usdc = IERC20(usdc_);
        tokenMessenger = ITokenMessengerV2(tokenMessenger_);
        for (uint256 i = 0; i < initialDomains.length; i++) {
            allowedDomain[initialDomains[i]] = true;
        }
    }

    function setDomainAllowed(uint32 domain, bool allowed) external onlyOwner {
        allowedDomain[domain] = allowed;
        emit DomainAllowlistChanged(domain, allowed);
    }

    /// Caller must hold USDC, approve this router, then call routeUSDC.
    function routeUSDC(
        uint256 amount,
        uint32  destinationDomain,
        bytes32 mintRecipient,
        uint256 maxFee,
        uint32  minFinalityThreshold
    ) external returns (uint64 nonce) {
        if (amount == 0) revert ZeroAmount();
        if (mintRecipient == bytes32(0)) revert ZeroRecipient();
        if (!allowedDomain[destinationDomain]) revert DomainNotAllowed();

        usdc.safeTransferFrom(msg.sender, address(this), amount);
        usdc.forceApprove(address(tokenMessenger), amount);

        nonce = tokenMessenger.depositForBurn(
            amount,
            destinationDomain,
            mintRecipient,
            address(usdc),
            bytes32(0), // destinationCaller open
            maxFee,
            minFinalityThreshold
        );

        emit Routed(nonce, destinationDomain, mintRecipient, amount, maxFee, minFinalityThreshold);
    }
}
