// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "openzeppelin-contracts/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "openzeppelin-contracts/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";
import {Pausable} from "openzeppelin-contracts/contracts/utils/Pausable.sol";
import {ReentrancyGuard} from "openzeppelin-contracts/contracts/utils/ReentrancyGuard.sol";

/// @title WhaleAttestation — skin-in-the-game opt-in bond for tracked whales (V3 mechanism).
///
/// Why this exists:
///   Most agentic copy-trading indices have NO economic alignment from the signal
///   source. A whale's previous performance becomes the signal; they get no upside
///   from helping the index work, and no downside if their strategy degrades and
///   the index follows them down.
///
///   WhaleAttestation flips this: a whale who opts in posts a USDC bond and accepts
///   a public attestation. The bond is locked while the index actively mirrors them.
///   If the off-chain rank-decay agent (selection_engine.py) evicts them for
///   performance decay above the threshold, the operator can call `slash` to
///   forfeit a portion (configurable up to MAX_SLASH_BPS) of their bond to the
///   index treasury — partial restitution for the holders who got mirrored
///   through the decay. After a cooldown, the whale can reclaim the remainder.
///
///   Mechanism is opt-in. Bond size is whatever the whale chooses. A whale with a
///   real edge picks a bond size that makes them comfortable; the public bond
///   size itself becomes the signal of conviction.
///
/// What this contract does NOT do:
///   - It does not require whales to opt in. The watchlist still includes
///     non-bonded whales; they just don't have skin-in-the-game and so don't
///     get the public "bonded" attestation badge.
///   - It does not auto-detect decay. The operator (rank-decay agent + human)
///     calls `slash(wallet, slashBps, evidenceCid)` after evicting a whale.
///   - It does not redistribute slash to holders directly — slash goes to a
///     beneficiary set at deploy (typically the index treasury).
///
/// V3 path:
///   1. Deploy WhaleAttestation with USDC + slash beneficiary + cooldown + max slash bps.
///   2. Operator calls `setRegisteredWhale(wallet, true)` for whales on the watchlist.
///   3. Whale calls `bond(amount)` with their own wallet (must equal an entry in the
///      registered set). Their attestation becomes public, queryable by the frontend.
///   4. Operator can call `slash(wallet, slashBps, evidenceCid)` if rank-decay evicts.
///      slashBps capped by MAX_SLASH_BPS (default 5000 = 50%); evidenceCid is the
///      IPFS/GitHub Pages CID of the eviction reasoning (anchors the slash to the
///      same provenance pattern the AllocationDecided event uses).
///   5. Whale calls `requestUnbond()` to start the cooldown timer; after
///      `unbondCooldown` seconds, `claimUnbond()` returns whatever remains of the bond.
contract WhaleAttestation is Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant BPS_DENOMINATOR = 10_000;

    IERC20  public immutable usdc;
    address public slashBeneficiary;     // where slashed bonds flow (default: index treasury)
    uint256 public maxSlashBps;          // hard cap on slash per event
    uint64  public unbondCooldown;       // seconds between requestUnbond and claimUnbond

    struct Attestation {
        uint256 bondAmount;          // USDC base units locked
        uint64  bondedAt;            // unix seconds
        uint64  unbondRequestedAt;   // 0 if not requested
        bool    registered;          // operator-managed allowlist
    }
    mapping(address => Attestation) public attestations;

    // -- events --
    event WhaleRegistered(address indexed wallet, bool registered);
    event Bonded(address indexed wallet, uint256 amount, uint256 totalBond);
    event Slashed(address indexed wallet, uint256 amount, uint16 slashBps, bytes32 evidenceCid);
    event UnbondRequested(address indexed wallet, uint64 cooldownEndsAt);
    event UnbondClaimed(address indexed wallet, uint256 amount);
    event SlashBeneficiaryChanged(address oldAddr, address newAddr);
    event MaxSlashBpsChanged(uint256 oldBps, uint256 newBps);
    event UnbondCooldownChanged(uint64 oldSec, uint64 newSec);

    // -- errors --
    error NotRegistered();
    error BondTooSmall();
    error NoBond();
    error AlreadyRequested();
    error CooldownNotElapsed();
    error SlashTooLarge();
    error MissingEvidenceCID();
    error ZeroAddress();
    error InvalidBps();
    error NoUnbondRequest();

    constructor(
        address usdc_,
        address slashBeneficiary_,
        uint256 maxSlashBps_,
        uint64  unbondCooldown_,
        address operator
    ) Ownable(operator) {
        if (usdc_ == address(0) || slashBeneficiary_ == address(0) || operator == address(0)) {
            revert ZeroAddress();
        }
        if (maxSlashBps_ == 0 || maxSlashBps_ > BPS_DENOMINATOR) revert InvalidBps();
        usdc = IERC20(usdc_);
        slashBeneficiary = slashBeneficiary_;
        maxSlashBps = maxSlashBps_;
        unbondCooldown = unbondCooldown_;
    }

    // ------------------------------------------------------------------
    // Operator (owner) functions
    // ------------------------------------------------------------------

    /// Allowlist a wallet for bonding. Operator adds wallets that appear on
    /// the off-chain curated watchlist.
    function setRegisteredWhale(address wallet, bool registered) external onlyOwner {
        attestations[wallet].registered = registered;
        emit WhaleRegistered(wallet, registered);
    }

    /// Slash a portion of `wallet`'s bond to the slashBeneficiary.
    /// Anchored to an off-chain evidence document (typically the same
    /// allocation-doc pattern used by AllocationDecided in RebalanceExecutor)
    /// via evidenceCid (32-byte keccak256 of the eviction reasoning).
    function slash(address wallet, uint16 slashBps, bytes32 evidenceCid)
        external
        nonReentrant
        onlyOwner
        whenNotPaused
    {
        if (slashBps == 0 || slashBps > maxSlashBps) revert SlashTooLarge();
        if (evidenceCid == bytes32(0)) revert MissingEvidenceCID();
        Attestation storage a = attestations[wallet];
        if (a.bondAmount == 0) revert NoBond();

        uint256 slashAmount = (a.bondAmount * slashBps) / BPS_DENOMINATOR;
        a.bondAmount -= slashAmount;
        usdc.safeTransfer(slashBeneficiary, slashAmount);
        emit Slashed(wallet, slashAmount, slashBps, evidenceCid);
    }

    function setSlashBeneficiary(address newAddr) external onlyOwner {
        if (newAddr == address(0)) revert ZeroAddress();
        emit SlashBeneficiaryChanged(slashBeneficiary, newAddr);
        slashBeneficiary = newAddr;
    }

    function setMaxSlashBps(uint256 newBps) external onlyOwner {
        if (newBps == 0 || newBps > BPS_DENOMINATOR) revert InvalidBps();
        emit MaxSlashBpsChanged(maxSlashBps, newBps);
        maxSlashBps = newBps;
    }

    function setUnbondCooldown(uint64 newSec) external onlyOwner {
        emit UnbondCooldownChanged(unbondCooldown, newSec);
        unbondCooldown = newSec;
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ------------------------------------------------------------------
    // Whale-facing functions
    // ------------------------------------------------------------------

    /// Whale posts a USDC bond. Their own wallet must already be in the
    /// registered set (operator-controlled). Multiple bond calls accumulate.
    function bond(uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert BondTooSmall();
        Attestation storage a = attestations[msg.sender];
        if (!a.registered) revert NotRegistered();
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        a.bondAmount += amount;
        // Reset the bondedAt timestamp on top-up so the on-chain age tracks the
        // most recent commitment.
        a.bondedAt = uint64(block.timestamp);
        // Top-up cancels any pending unbond request — re-commit to the index.
        a.unbondRequestedAt = 0;
        emit Bonded(msg.sender, amount, a.bondAmount);
    }

    /// Whale requests to unbond. Starts the cooldown; bond remains slashable
    /// during the cooldown so a whale can't escape decay by front-running.
    function requestUnbond() external whenNotPaused {
        Attestation storage a = attestations[msg.sender];
        if (a.bondAmount == 0) revert NoBond();
        if (a.unbondRequestedAt != 0) revert AlreadyRequested();
        a.unbondRequestedAt = uint64(block.timestamp);
        emit UnbondRequested(msg.sender, uint64(block.timestamp) + unbondCooldown);
    }

    /// After the cooldown, the whale reclaims whatever remains of the bond.
    function claimUnbond() external nonReentrant whenNotPaused {
        Attestation storage a = attestations[msg.sender];
        if (a.bondAmount == 0) revert NoBond();
        if (a.unbondRequestedAt == 0) revert NoUnbondRequest();
        if (block.timestamp < uint256(a.unbondRequestedAt) + uint256(unbondCooldown)) {
            revert CooldownNotElapsed();
        }
        uint256 amount = a.bondAmount;
        a.bondAmount = 0;
        a.unbondRequestedAt = 0;
        a.bondedAt = 0;
        usdc.safeTransfer(msg.sender, amount);
        emit UnbondClaimed(msg.sender, amount);
    }

    // ------------------------------------------------------------------
    // Views
    // ------------------------------------------------------------------

    function isBonded(address wallet) external view returns (bool) {
        return attestations[wallet].bondAmount > 0;
    }

    function bondAmount(address wallet) external view returns (uint256) {
        return attestations[wallet].bondAmount;
    }

    function unbondEligibleAt(address wallet) external view returns (uint64) {
        Attestation storage a = attestations[wallet];
        if (a.unbondRequestedAt == 0) return 0;
        return a.unbondRequestedAt + unbondCooldown;
    }
}
