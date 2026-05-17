// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// USYC integration shape (Circle's tokenised money market fund).
// V1 against an ERC-4626-style vault interface; Phase 2 swaps to Circle's published USYC address.
interface IUSYC {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets);
    function convertToAssets(uint256 shares) external view returns (uint256 assets);
    function balanceOf(address account) external view returns (uint256);
    function asset() external view returns (address);
}
