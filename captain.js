/**
 * captain.js — Fentheris shared captain data layer
 * ============================================================
 * Single source of truth for the player's surface captain.
 * Loaded by both index.html and surface.html via <script src="captain.js">.
 *
 * RESPONSIBILITIES:
 *   - Captain schema and safe defaults
 *   - Persistent save/load via localStorage ('fentheris_captain')
 *   - All stat mutations (XP, HP, defense, inventory)
 *   - Level-up logic and XP thresholds
 *   - Gear equip/unequip with stat recalculation
 *
 * NOT RESPONSIBLE FOR:
 *   - DOM rendering (each HTML handles its own UI)
 *   - Combat flow (surface.html handles surface combat)
 *   - Ship combat (index.html handles space combat)
 *   - Sound effects (each HTML has its own sfx system)
 *   - SessionStorage handshake between files (still used for gold/day/hours)
 *
 * USAGE:
 *   Call loadCaptain() on page init.
 *   Call saveCaptain() after any mutation.
 *   Use Captain.* functions for all stat changes.
 *
 * FUTURE:
 *   When moving to a proper JS app, this file becomes a module:
 *   export default Captain;
 *   or split into captain-data.js + captain-combat.js as needed.
 * ============================================================
 */

// ── Storage key ───────────────────────────────────────────────────────────────
const CAPTAIN_STORAGE_KEY = 'fentheris_captain';

// ── Default captain template ──────────────────────────────────────────────────
// Matches the schema used by surface.html S.captain and index.html G.captain.
// Edit defaults here — both files will pick them up automatically.
const CAPTAIN_DEFAULTS = {
  level:       1,
  xp:          0,
  hp:          30,
  maxHp:       30,    // recalculated by recalcStats() when gear changes
  defense:     0,     // recalculated by recalcStats()
  initiative:  0,

  // ── Starting gear ──────────────────────────────────────────────────────────
  // These are the starter items given on first descent.
  // Upgraded gear replaces these objects entirely.
  melee: {
    name:       'Combat Knife',
    dmgMin:     3,
    dmgMax:     6,
    type:       'melee',
  },
  ranged: {
    name:           'Void Pistol',
    dmgMin:         6,
    dmgMax:         10,
    type:           'ranged',
    shotsPerCombat: 3,
  },
  armor: {
    name:     'Leather Armor',
    hpBonus:  8,
    def:      1,
  },
  helmet: {
    name:     'Void Helmet',
    hpBonus:  4,
    def:      1,
  },

  // ── Runtime state ──────────────────────────────────────────────────────────
  shotsLoaded: 3,   // current pistol magazine
  inv:         [],  // unified inventory (same array as G.ship.inv in space)
  gearGiven:   false, // true after initStarterGear() runs once
};

// ── XP threshold per level ────────────────────────────────────────────────────
// Level N requires N * 100 XP to advance to N+1.
// Simple linear curve — adjust the multiplier here to rebalance.
function xpToNext(level) {
  return level * 100;
}

// ── Stat recalculation ────────────────────────────────────────────────────────
// Call after any gear change. Recomputes maxHp and defense from equipped items.
// Clamps current HP to new maxHp so over-healing can't happen on equip.
function recalcStats(cap) {
  const armorHp  = (cap.armor  && cap.armor.hpBonus)  ? cap.armor.hpBonus  : 0;
  const helmetHp = (cap.helmet && cap.helmet.hpBonus) ? cap.helmet.hpBonus : 0;
  const armorDef = (cap.armor  && cap.armor.def)      ? cap.armor.def      : 0;
  const helmDef  = (cap.helmet && cap.helmet.def)      ? cap.helmet.def     : 0;

  const baseHp   = 30 + (cap.level - 1) * 5; // +5 maxHp per level beyond 1
  cap.maxHp      = baseHp + armorHp + helmetHp;
  cap.defense    = armorDef + helmDef;

  // Don't let current HP exceed new max
  if (cap.hp > cap.maxHp) cap.hp = cap.maxHp;

  return cap;
}

// ── Level-up check ────────────────────────────────────────────────────────────
// Called internally after gainXP. Returns true if a level-up occurred.
// Handles cascading multi-level gains (e.g. large XP reward).
function _checkLevelUp(cap) {
  let leveled = false;
  while (cap.xp >= xpToNext(cap.level)) {
    cap.xp   -= xpToNext(cap.level);
    cap.level += 1;
    leveled    = true;
    // Recalc stats on level-up (maxHp scales with level)
    recalcStats(cap);
    // Fully heal on level-up
    cap.hp = cap.maxHp;
  }
  return leveled;
}

// ══════════════════════════════════════════════════════════════════════════════
// Captain namespace — all public mutation functions
// ══════════════════════════════════════════════════════════════════════════════
const Captain = {

  /**
   * gainXP(cap, amount)
   * Add XP to the captain. Handles level-ups automatically.
   * Returns { leveled: bool, newLevel: number }
   */
  gainXP(cap, amount) {
    cap.xp = (cap.xp || 0) + amount;
    const leveled = _checkLevelUp(cap);
    saveCaptain(cap);
    return { leveled, newLevel: cap.level };
  },

  /**
   * takeDamage(cap, amount)
   * Reduce HP by amount (after defense). Returns actual damage dealt.
   * HP is floored at 0 — caller checks cap.hp <= 0 for death.
   */
  takeDamage(cap, amount) {
    const effective = Math.max(1, amount - (cap.defense || 0));
    cap.hp = Math.max(0, (cap.hp || 0) - effective);
    saveCaptain(cap);
    return effective;
  },

  /**
   * healHP(cap, amount)
   * Restore HP by amount, capped at maxHp.
   * Returns actual amount healed.
   */
  healHP(cap, amount) {
    const before = cap.hp || 0;
    cap.hp = Math.min(cap.maxHp || 30, before + amount);
    saveCaptain(cap);
    return cap.hp - before;
  },

  /**
   * fullHeal(cap)
   * Set HP to maxHp (used on rest, clinic visit).
   */
  fullHeal(cap) {
    cap.hp = cap.maxHp || 30;
    saveCaptain(cap);
  },

  /**
   * equipItem(cap, item, slot)
   * Equip an item to a gear slot ('melee'|'ranged'|'armor'|'helmet').
   * Removes the item from inventory if it came from there.
   * Returns the previously equipped item (or null).
   */
  equipItem(cap, item, slot) {
    const valid = ['melee','ranged','armor','helmet'];
    if (!valid.includes(slot)) return null;
    const prev = cap[slot] || null;
    cap[slot] = item;
    // Remove from inventory if present
    cap.inv = (cap.inv || []).filter(i => i !== item);
    recalcStats(cap);
    saveCaptain(cap);
    return prev;
  },

  /**
   * unequipItem(cap, slot)
   * Unequip a gear slot and move item back to inventory.
   * Returns the unequipped item (or null if slot was empty).
   */
  unequipItem(cap, slot) {
    const item = cap[slot] || null;
    if (!item) return null;
    cap[slot] = null;
    cap.inv = cap.inv || [];
    cap.inv.push(item);
    recalcStats(cap);
    saveCaptain(cap);
    return item;
  },

  /**
   * addToInv(cap, item)
   * Add an item to inventory. Stacks by id if item has qty field.
   */
  addToInv(cap, item) {
    cap.inv = cap.inv || [];
    if (item.id && item.qty) {
      const existing = cap.inv.find(i => i.id === item.id);
      if (existing) {
        existing.qty = (existing.qty || 1) + (item.qty || 1);
        saveCaptain(cap);
        return;
      }
    }
    cap.inv.push(item);
    saveCaptain(cap);
  },

  /**
   * removeFromInv(cap, itemId, qty)
   * Remove qty units of itemId from inventory.
   * Returns true if successful, false if item not found.
   */
  removeFromInv(cap, itemId, qty) {
    qty = qty || 1;
    cap.inv = cap.inv || [];
    const slot = cap.inv.find(i => i.id === itemId);
    if (!slot) return false;
    slot.qty = (slot.qty || 1) - qty;
    if (slot.qty <= 0) cap.inv = cap.inv.filter(i => i !== slot);
    saveCaptain(cap);
    return true;
  },

  /**
   * reload(cap)
   * Reload the ranged weapon from a magazine in inventory.
   * Returns true if reload succeeded.
   */
  reload(cap) {
    if (!cap.ranged) return false;
    const mag = cap.inv.find(i => i.type === 'ammo');
    if (!mag) return false;
    Captain.removeFromInv(cap, mag.id, 1);
    cap.shotsLoaded = cap.ranged.shotsPerCombat || 3;
    saveCaptain(cap);
    return true;
  },

  /**
   * applyPenalty(cap, tsPenalty, xpPenalty)
   * Apply gold and XP penalties (used on defeat/death).
   * XP cannot go below 0. Gold floor is 0.
   * Returns { tsPenalty, xpPenalty } (actual amounts deducted).
   */
  applyPenalty(cap, gold, tsPenaltyFrac, xpPenaltyFrac) {
    const tsCut = Math.ceil((gold || 0) * (tsPenaltyFrac || 0.1));
    const xpCut = Math.ceil((cap.xp || 0) * (xpPenaltyFrac || 0.1));
    cap.xp = Math.max(0, (cap.xp || 0) - xpCut);
    cap.hp = 1; // always wake at 1 HP
    saveCaptain(cap);
    return { tsCut, xpCut };
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// Persistence — localStorage under CAPTAIN_STORAGE_KEY
// ══════════════════════════════════════════════════════════════════════════════

/**
 * saveCaptain(cap)
 * Persist the captain object to localStorage.
 * Call after any mutation. Silently fails if storage is unavailable.
 */
function saveCaptain(cap) {
  try {
    localStorage.setItem(CAPTAIN_STORAGE_KEY, JSON.stringify(cap));
  } catch(e) {
    // localStorage unavailable (private mode, quota exceeded) — fail silently.
    // The in-memory object is still correct for this session.
  }
}

/**
 * loadCaptain()
 * Load the captain from localStorage.
 * Returns a full captain object — uses CAPTAIN_DEFAULTS for any missing fields.
 * Safe to call on first load (returns defaults if nothing stored yet).
 */
function loadCaptain() {
  try {
    const raw = localStorage.getItem(CAPTAIN_STORAGE_KEY);
    if (raw) {
      const stored = JSON.parse(raw);
      // Merge with defaults so new fields added to CAPTAIN_DEFAULTS
      // are automatically available even in old saves.
      const cap = Object.assign({}, CAPTAIN_DEFAULTS, stored);
      // Always recalc stats on load to catch any schema changes
      recalcStats(cap);
      return cap;
    }
  } catch(e) {
    // Corrupt data — fall through to defaults
  }
  // First load or corrupt save — return a fresh captain
  const cap = Object.assign({}, CAPTAIN_DEFAULTS);
  recalcStats(cap);
  return cap;
}

/**
 * clearCaptain()
 * Wipe captain from localStorage (new game / hard reset).
 */
function clearCaptain() {
  try { localStorage.removeItem(CAPTAIN_STORAGE_KEY); } catch(e) {}
}

/**
 * mergeCaptainFromEntry(cap, entryData)
 * Merge captain data arriving from the sessionStorage handshake (index→surface).
 * Only updates fields that are present and non-null in entryData.captain.
 * Does NOT wipe fields that are absent — prevents gear loss on partial entries.
 */
function mergeCaptainFromEntry(cap, entryData) {
  if (!entryData || !entryData.captain) return cap;
  const incoming = entryData.captain;
  // Merge top-level scalar fields
  const scalars = ['level','xp','hp','maxHp','defense','initiative','shotsLoaded','gearGiven'];
  scalars.forEach(k => {
    if (incoming[k] != null) cap[k] = incoming[k];
  });
  // Merge gear slots only if they exist in incoming
  ['melee','ranged','armor','helmet'].forEach(slot => {
    if (incoming[slot]) cap[slot] = incoming[slot];
  });
  // Merge inventory — prefer incoming if non-empty
  if (incoming.inv && incoming.inv.length > 0) cap.inv = incoming.inv;
  recalcStats(cap);
  saveCaptain(cap);
  return cap;
}

// ══════════════════════════════════════════════════════════════════════════════
// Exported surface for use without module system
// ══════════════════════════════════════════════════════════════════════════════
// Since we're not using ES modules yet, all functions above are global.
// In a future module refactor:
//   export { Captain, loadCaptain, saveCaptain, clearCaptain,
//            mergeCaptainFromEntry, xpToNext, recalcStats };
