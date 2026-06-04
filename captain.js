/**
 * captain.js — Fentheris shared captain data layer  v3
 * =====================================================
 * DESIGN RULES (per ChatGPT audit):
 *
 *   sessionStorage = authoritative DURING page transitions
 *   localStorage   = authoritative BETWEEN browser sessions (permanent save)
 *
 *   Never let localStorage overwrite data just passed through sessionStorage.
 *   No merging. No gearGiven gating on inventory.
 *   Inventory stored once on the captain object — G.ship.inv references it.
 *
 * TRANSITION FLOW:
 *   index  → surface : sessionStorage entry  (captain + gold)  wins on load
 *   surface → index  : sessionStorage exit   (captain + gold + inv) wins on load
 *   localStorage written after every mutation and after every transition
 *
 * USAGE:
 *   loadCaptain()    — read from localStorage (permanent save)
 *   saveCaptain(cap) — write to localStorage
 *   freshCaptain()   — brand-new default captain (only if no save exists)
 */

const CAPTAIN_KEY = 'fentheris_captain';

// ── Default captain (only used when no localStorage save exists) ──────────────
function freshCaptain() {
  return {
    level:         1,
    xp:            0,
    hp:            30,
    maxHp:         30,
    defense:       0,
    initiative:    0,
    regenRounds:   0,
    regenPerRound: 0,
    shotsLoaded:   3,
    gearGiven:     false,
    gold:          150,   // mirrored from G.ship.gold / S.gold
    inv:           [],    // single authoritative inventory list
    melee:  { name:'Combat Knife',  dmgMin:3,  dmgMax:6,  type:'melee' },
    ranged: { name:'Void Pistol',   dmgMin:6,  dmgMax:10, type:'ranged', shotsPerCombat:3 },
    armor:  { name:'Leather Armor', hpBonus:8, def:1 },
    helmet: { name:'Void Helmet',   hpBonus:4, def:1 },
  };
}

// ── XP curve ─────────────────────────────────────────────────────────────────
function xpToNext(level) { return level * 100; }

// ── Stat recalculation (always call after gear changes or level-up) ───────────
function recalcStats(cap) {
  const base    = 30 + ((cap.level || 1) - 1) * 5;
  const armorHp = (cap.armor  && cap.armor.hpBonus)  || 0;
  const helmHp  = (cap.helmet && cap.helmet.hpBonus) || 0;
  cap.maxHp   = base + armorHp + helmHp;
  cap.defense = ((cap.armor && cap.armor.def) || 0) + ((cap.helmet && cap.helmet.def) || 0);
  if (cap.hp > cap.maxHp) cap.hp = cap.maxHp;
  return cap;
}

// ── Persistence ───────────────────────────────────────────────────────────────
function saveCaptain(cap) {
  if (!cap) return;
  try { localStorage.setItem(CAPTAIN_KEY, JSON.stringify(cap)); } catch(_) {}
}

function loadCaptain() {
  try {
    const raw = localStorage.getItem(CAPTAIN_KEY);
    if (raw) return JSON.parse(raw);
  } catch(e) {
    console.error('Captain save corrupted — resetting to defaults.');
  }
  return freshCaptain();
}

function clearCaptain() {
  try { localStorage.removeItem(CAPTAIN_KEY); } catch(_) {}
}

// ── Level-up helper ───────────────────────────────────────────────────────────
function _checkLevelUp(cap) {
  let leveled = false;
  while (cap.xp >= xpToNext(cap.level)) {
    cap.xp   -= xpToNext(cap.level);
    cap.level += 1;
    leveled    = true;
    recalcStats(cap);
    cap.hp = cap.maxHp;
  }
  return leveled;
}

// ── Captain mutation API ──────────────────────────────────────────────────────
// Every method calls saveCaptain() so localStorage stays current.
const Captain = {

  gainXP(cap, amount) {
    cap.xp = (cap.xp || 0) + amount;
    const leveled = _checkLevelUp(cap);
    saveCaptain(cap);
    return { leveled, newLevel: cap.level };
  },

  takeDamage(cap, rawAmount) {
    const dmg = Math.max(1, rawAmount - (cap.defense || 0));
    cap.hp = Math.max(0, (cap.hp || 0) - dmg);
    saveCaptain(cap);
    return dmg;
  },

  healHP(cap, amount) {
    const before = cap.hp || 0;
    cap.hp = Math.min(cap.maxHp || 30, before + amount);
    saveCaptain(cap);
    return cap.hp - before;
  },

  fullHeal(cap) {
    cap.hp = cap.maxHp || 30;
    saveCaptain(cap);
  },

  applyPenalty(cap, gold, tsFrac, xpFrac) {
    const tsCut = Math.ceil((gold || 0) * (tsFrac || 0.10));
    const xpCut = Math.ceil((cap.xp || 0) * (xpFrac || 0.10));
    cap.xp = Math.max(0, (cap.xp || 0) - xpCut);
    cap.hp = 1;
    saveCaptain(cap);
    return { tsCut, xpCut };
  },

  addToInv(cap, item) {
    cap.inv = cap.inv || [];
    if (item.id) {
      const ex = cap.inv.find(i => i.id === item.id);
      if (ex) { ex.qty = (ex.qty || 1) + (item.qty || 1); saveCaptain(cap); return; }
    }
    cap.inv.push(item);
    saveCaptain(cap);
  },

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

  equipItem(cap, item, slot) {
    if (!['melee','ranged','armor','helmet'].includes(slot)) return null;
    const prev = cap[slot] || null;
    cap[slot] = item;
    cap.inv = (cap.inv || []).filter(i => i !== item);
    recalcStats(cap);
    saveCaptain(cap);
    return prev;
  },

  reload(cap) {
    if (!cap.ranged) return false;
    const mag = (cap.inv || []).find(i => i.type === 'ammo');
    if (!mag) return false;
    Captain.removeFromInv(cap, mag.id, 1);
    cap.shotsLoaded = cap.ranged.shotsPerCombat || 3;
    saveCaptain(cap);
    return true;
  },

  // ── Transition helpers ──────────────────────────────────────────────────────
  // Call these at file boundaries. sessionStorage packet wins over localStorage.

  /** Before navigating away from either file. */
  onExit(cap) {
    if (!cap) return;
    recalcStats(cap);
    saveCaptain(cap);
  },

  /** On page load — reads localStorage (permanent save). */
  onEntry() {
    return loadCaptain();
  },

  /** Ensure localStorage is current without changing anything. */
  syncNow(cap) {
    if (!cap) return;
    recalcStats(cap);
    saveCaptain(cap);
  },
};

// No ES module export yet — all symbols are global.
// Future: export { Captain, loadCaptain, saveCaptain, clearCaptain, freshCaptain, xpToNext, recalcStats };
