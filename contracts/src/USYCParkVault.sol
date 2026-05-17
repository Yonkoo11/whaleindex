// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {IUSYC} from "./interfaces/IUSYC.sol";

/// @title USYCParkVault — parks idle USDC into Circle USYC for yield between rebalances.
/// Owner = RebalanceExecutor. Only owner can park/unpark.
contract USYCParkVault is Ownable {
    using SafeERC20 for IERC20;

    IERC20 public immutable usdc;
    IUSYC  public immutable usyc;

    event Parked(uint256 usdcIn, uint256 sharesOut);
    event Unparked(uint256 sharesBurned, uint256 usdcOut);

    constructor(address usdc_, address usyc_, address executor) Ownable(executor) {
        usdc = IERC20(usdc_);
        usyc = IUSYC(usyc_);
    }

    function park(uint256 amount) external onlyOwner returns (uint256 shares) {
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        usdc.forceApprove(address(usyc), amount);
        shares = usyc.deposit(amount, address(this));
        emit Parked(amount, shares);
    }

    function unpark(uint256 shares) external onlyOwner returns (uint256 assets) {
        assets = usyc.redeem(shares, msg.sender, address(this));
        emit Unparked(shares, assets);
    }

    /// USDC-denominated value of vault holdings (idle + USYC shares marked to current rate).
    function balanceUSDC() external view returns (uint256) {
        uint256 idle = usdc.balanceOf(address(this));
        uint256 shares = usyc.balanceOf(address(this));
        uint256 sharesAsAssets = shares == 0 ? 0 : usyc.convertToAssets(shares);
        return idle + sharesAsAssets;
    }
}
