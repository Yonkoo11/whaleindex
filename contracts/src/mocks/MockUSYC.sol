// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "openzeppelin-contracts/contracts/token/ERC20/ERC20.sol";
import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {IUSYC} from "../interfaces/IUSYC.sol";

/// Mock for Circle USYC. 1:1 deposit/redeem with no yield accrual in tests.
/// Phase 2 swaps this for the live USYC address with real yield.
contract MockUSYC is ERC20, IUSYC {
    using SafeERC20 for IERC20;

    IERC20 public immutable underlying;

    constructor(address underlying_) ERC20("Mock USYC", "USYC") {
        underlying = IERC20(underlying_);
    }

    function decimals() public pure override returns (uint8) { return 6; }

    function deposit(uint256 assets, address receiver) external override returns (uint256 shares) {
        underlying.safeTransferFrom(msg.sender, address(this), assets);
        shares = assets; // 1:1 for V1 mock
        _mint(receiver, shares);
    }

    function redeem(uint256 shares, address receiver, address owner_) external override returns (uint256 assets) {
        require(msg.sender == owner_ || allowance(owner_, msg.sender) >= shares, "USYC: not authorized");
        _burn(owner_, shares);
        assets = shares;
        underlying.safeTransfer(receiver, assets);
    }

    function convertToAssets(uint256 shares) external pure override returns (uint256) { return shares; }
    function asset() external view override returns (address) { return address(underlying); }

    function balanceOf(address account) public view override(ERC20, IUSYC) returns (uint256) {
        return ERC20.balanceOf(account);
    }
}
