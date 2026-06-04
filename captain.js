/**
 * captain.js — Fentheris shared captain data layer  v2
 * =====================================================
 * ARCHITECTURE:
 *   localStorage['fentheris_captain'] is the ONE source of truth.
 *   Both index.html and surface.html call loadCaptain() on init.
 *   Every mutation calls saveCaptain() immediately.
 *   Captain data does NOT travel through sessionStorage.
 *   sessionStorage carries only: gold, day, hours, shipType, shipName.
 *
 * USAGE:
 *   On page load  → cap = loadCaptain()
 *   On any change → saveCaptain(cap)   (automatic inside Captain.* functions)
 *   New game      → cap = freshCaptain(); saveCaptain(cap)
 *   Hard reset    → clearCaptain()
 */

const CAPTAIN_KEY = 'fentheris_captain';

// ── Default schema ────────────────────────────────────────────────────────────
function freshCaptain() {
  return {
    level:       1,
    xp:          0,
    hp:          30,
    maxHp:       30,
    defense:     0,
    initiative:  0,
    regenRounds: 0,
    regenPerRound: 0,
    shotsLoaded: 3,
    gearGiven:   false,
    inv:         [],
    melee:  { name:'Combat Knife', dmgMin:3,  dmgMax:6,  type:'melee' },
    ranged: { name:'Void Pistol',  dmgMin:6,  dmgMax:10, type:'ranged', shotsPerCombat:3 },
    armor:  { name:'Leather Armor', hpBonus:8, def:1 },
    helmet: { name:'Void Helmet',   hpBonus:4, def:1 },
  };
}

// ── XP curve ─────────────────────────────────────────────────────────────────
function xpToNext(level) { return level * 100; }

// ── Stat recalculation ────────────────────────────────────────────────────────
function recalcStats(cap) {
  const base    = 30 + ((cap.level || 1) - 1) * 5;
  const armorHp = (cap.armor  && cap.armor.hpBonus)  || 0;
  const helmHp  = (cap.helmet && cap.helmet.hpBonus) || 0;
  const armorDef= (cap.armor  && cap.armor.def)       || 0;
  const helmDef = (cap.helmet && cap.helmet.def)      || 0;
  cap.maxHp   = base + armorHp + helmHp;
  cap.defense = armorDef + helmDef;
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
    if (raw) {
      const stored = JSON.parse(raw);
      // Forward-fill any fields added after original save
      const cap = Object.assign(freshCaptain(), stored);
      recalcStats(cap);
      return cap;
    }
  } catch(_) {}
  return freshCaptain();
}

function clearCaptain() {
  try { localStorage.removeItem(CAPTAIN_KEY); } catch(_) {}
}

// ── Level-up ──────────────────────────────────────────────────────────────────
function _checkLevelUp(cap) {
  let leveled = false;
  while (cap.xp >= xpToNext(cap.level)) {
    cap.xp   -= xpToNext(cap.level);
    cap.level += 1;
    leveled    = true;
    recalcStats(cap);
    cap.hp = cap.maxHp; // full heal on level up
  }
  return leveled;
}

// ── Captain mutation API ──────────────────────────────────────────────────────
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
    tsFrac = tsFrac || 0.10;
    xpFrac = xpFrac || 0.10;
    const tsCut = Math.ceil((gold || 0) * tsFrac);
    const xpCut = Math.ceil((cap.xp || 0) * xpFrac);
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
    const valid = ['melee','ranged','armor','helmet'];
    if (!valid.includes(slot)) return null;
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
};

// ── mergeCaptainFromEntry ─────────────────────────────────────────────────────
// Used when sessionStorage entry has captain data (legacy path / first descent).
// Merges scalars only — inventory always comes from localStorage.
function mergeCaptainFromEntry(cap, entryData) {
  if (!entryData) return cap;
  const inc = entryData.captain || entryData;
  if (!inc) return cap;
  // Scalars
  ['level','xp','hp','maxHp','defense','initiative','shotsLoaded','gearGiven',
   'regenRounds','regenPerRound'].forEach(k => {
    if (inc[k] != null) cap[k] = inc[k];
  });
  // Gear slots
  ['melee','ranged','armor','helmet'].forEach(slot => {
    if (inc[slot]) cap[slot] = inc[slot];
  });
  // Inventory: ONLY use entry inv on very first descent (gearGiven just set)
  // After that, localStorage inv is always authoritative.
  if (inc.gearGiven && !(cap.gearGiven) && inc.inv && inc.inv.length > 0) {
    cap.inv = inc.inv;
  }
  cap.gearGiven = inc.gearGiven || cap.gearGiven;
  recalcStats(cap);
  saveCaptain(cap);
  return cap;
}

// Future module export:
// export { Captain, loadCaptain, saveCaptain, clearCaptain,
//          freshCaptain, xpToNext, recalcStats, mergeCaptainFromEntry };

// ══════════════════════════════════════════════════════════════════════════════
// TRANSITION HOOKS
// ══════════════════════════════════════════════════════════════════════════════
// Call these at every file boundary. Both files use the same localStorage key
// so there is no merge, no sync, no sessionStorage involvement for captain.
// Just save on exit, load on entry.

/**
 * Captain.onExit(cap)
 * Call immediately before navigating away (returnToShip, descendToSurface).
 * Writes the full captain to localStorage so the destination file finds it.
 */
Captain.onExit = function(cap) {
  if (!cap) return;
  recalcStats(cap);           // ensure maxHp/defense are current
  saveCaptain(cap);           // flush to localStorage
};

/**
 * Captain.onEntry()
 * Call at the very start of init() in either file.
 * Reads from localStorage and returns a fully initialised captain.
 * Never returns null — falls back to freshCaptain() if nothing is stored.
 */
Captain.onEntry = function() {
  return loadCaptain();       // always localStorage; never defaults unless truly first run
};

/**
 * Captain.syncNow(cap)
 * Call any time you want to guarantee localStorage is current.
 * Idempotent — safe to call frequently.
 */
Captain.syncNow = function(cap) {
  if (!cap) return;
  recalcStats(cap);
  saveCaptain(cap);
};
