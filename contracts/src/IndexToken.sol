// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "openzeppelin-contracts/contracts/utils/ReentrancyGuard.sol";
import {NAVOracle} from "./NAVOracle.sol";

/// @title IndexToken — USDC-denominated index ERC-20 for WhaleIndex.
/// Mint: deposit USDC, receive index shares at current NAV-per-share.
/// Redeem: burn shares, receive USDC at current NAV-per-share.
/// NAV is read from NAVOracle; reads revert if the oracle is stale.
contract IndexToken is ERC20, Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20    public immutable usdc;
    NAVOracle public immutable nav;

    /// First minter gets shares at 1:1 (1 USDC unit = 1 wei share when adjusted for decimals).
    /// Subsequent mints use shares = amountUSDC * totalSupply / navUSDC.
    /// Both USDC (6dec) and share token (18dec) are denominated cleanly via SHARE_SCALE.
    uint256 public constant SHARE_SCALE = 1e12; // 18-dec shares vs 6-dec USDC

    event Bought(address indexed buyer, uint256 usdcIn, uint256 sharesOut);
    event Redeemed(address indexed seller, uint256 sharesIn, uint256 usdcOut);

    error StaleNAV();
    error ZeroAmount();
    error InsufficientLiquidity();

    constructor(address usdc_, address navOracle_, address owner_)
        ERC20("WhaleIndex Token", "WHALE")
        Ownable(owner_)
    {
        usdc = IERC20(usdc_);
        nav  = NAVOracle(navOracle_);
    }

    /// Buyer pays USDC; receives shares proportional to current NAV.
    function buy(uint256 usdcAmount) external nonReentrant returns (uint256 sharesOut) {
        if (usdcAmount == 0) revert ZeroAmount();

        usdc.safeTransferFrom(msg.sender, address(this), usdcAmount);

        uint256 supply = totalSupply();
        if (supply == 0) {
            sharesOut = usdcAmount * SHARE_SCALE;
        } else {
            (uint256 navUsdc, bool fresh) = nav.getNAV();
            if (!fresh) revert StaleNAV();
            // shares = supply * amountIn / navUsdc
            sharesOut = (supply * usdcAmount) / navUsdc;
        }

        _mint(msg.sender, sharesOut);
        emit Bought(msg.sender, usdcAmount, sharesOut);
    }

    /// Burn shares for USDC at current NAV.
    function redeem(uint256 sharesIn) external nonReentrant returns (uint256 usdcOut) {
        if (sharesIn == 0) revert ZeroAmount();

        (uint256 navUsdc, bool fresh) = nav.getNAV();
        if (!fresh) revert StaleNAV();

        uint256 supply = totalSupply();
        usdcOut = (navUsdc * sharesIn) / supply;

        if (usdcOut > usdc.balanceOf(address(this))) revert InsufficientLiquidity();

        _burn(msg.sender, sharesIn);
        usdc.safeTransfer(msg.sender, usdcOut);
        emit Redeemed(msg.sender, sharesIn, usdcOut);
    }

    /// Owner (RebalanceExecutor) can sweep USDC to the router during a rebalance.
    /// Caller pulls; nothing escapes the protocol that the owner can't trace.
    function withdrawForRebalance(address to, uint256 amount) external onlyOwner {
        usdc.safeTransfer(to, amount);
    }

    function sharePrice() external view returns (uint256) {
        uint256 supply = totalSupply();
        if (supply == 0) return 1e6; // initial price = 1 USDC per share (6 decimals)
        (uint256 navUsdc,) = nav.getNAV();
        return (navUsdc * SHARE_SCALE) / supply;
    }
}
