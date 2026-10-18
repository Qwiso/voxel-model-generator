"""
What a character is made of and wears, as the generator needs it: the skeleton every model is
skinned to, the body's regions, the items, the looks and the clips. The game's copy of these is in
`shared/src/character.rs`; keep the two the same.

Ported from bellweather-v2 (commit 3ea05c9, `packages/shared/src/character.ts`).
"""

# The armature, parents before children, in the order every model's skin lists its joints. The
# names are Blender's (Rigify-like, _L/_R for the character's own left and right). The character
# faces +z; its left is +x.
BONES = (
    "root", "hips", "spine", "chest", "neck", "head",
    "shoulder_L", "upper_arm_L", "forearm_L", "hand_L",
    "shoulder_R", "upper_arm_R", "forearm_R", "hand_R",
    "thigh_L", "shin_L", "foot_L",
    "thigh_R", "shin_R", "foot_R",
    "grip_L", "grip_R", "reel", "rod_1", "rod_2", "rod_3", "rod_tip",
)  # fmt: skip
# The last seven carry what the hands hold: `grip_<side>` sits in the middle of each fist (anything
# held there hangs from it), and a fishing pole's reel crank and rod, jointed so the rod can bend,
# hang from the right one. Nothing of the body moves with them.

BONE_PARENT = {
    "root": None,
    "hips": "root",
    "spine": "hips",
    "chest": "spine",
    "neck": "chest",
    "head": "neck",
    "shoulder_L": "chest",
    "upper_arm_L": "shoulder_L",
    "forearm_L": "upper_arm_L",
    "hand_L": "forearm_L",
    "shoulder_R": "chest",
    "upper_arm_R": "shoulder_R",
    "forearm_R": "upper_arm_R",
    "hand_R": "forearm_R",
    "thigh_L": "hips",
    "shin_L": "thigh_L",
    "foot_L": "shin_L",
    "thigh_R": "hips",
    "shin_R": "thigh_R",
    "foot_R": "shin_R",
    "grip_L": "hand_L",
    "grip_R": "hand_R",
    "reel": "grip_R",
    "rod_1": "grip_R",
    "rod_2": "rod_1",
    "rod_3": "rod_2",
    "rod_tip": "rod_3",
}

BODY_REGIONS = ("head", "ears", "torso", "upper_arms", "forearms", "hands", "hips", "legs", "feet")

# Every item there is: (slot, parts of the body it hides, other slots it covers).
ITEMS = {
    "leather_cap": ("head", ("hair",), ()),
    "horned_helm": ("head", ("hair",), ()),
    "hood": ("head", ("hair", "ears"), ("ears",)),
    "gold_amulet": ("neck", (), ()),
    "bead_necklace": ("neck", (), ()),
    "linen_tunic": ("chest", (), ()),
    "leather_jerkin": ("chest", (), ()),
    "steel_cuirass": ("chest", (), ()),
    "leather_bracers": ("arms", (), ()),
    "steel_pauldrons": ("arms", (), ()),
    "leather_gloves": ("gloves", ("hands",), ("ring1", "ring2")),
    "plate_gauntlets": ("gloves", ("hands",), ("ring1", "ring2")),
    "leather_belt": ("belt", (), ()),
    "gold_belt": ("belt", (), ()),
    "wool_trousers": ("legs", (), ()),
    "plated_tassets": ("legs", (), ()),
    "leather_boots": ("feet", ("feet",), ()),
    "iron_sabatons": ("feet", ("feet",), ()),
    "gold_hoops": ("ears", (), ()),
    "gem_studs": ("ears", (), ()),
    "gold_band": ("ring", (), ()),
    "ruby_ring": ("ring", (), ()),
    # Held in the right hand, and only while it's at work (the clips that use a tool, TOOL_CLIPS).
    "fishing_pole": ("tool", (), ()),
}
ITEM_IDS = tuple(ITEMS)

# The pieces of a face, each a mesh of its own (body.py draws them).
EYE_STYLES = ("round", "narrow", "wide", "small", "fierce", "sleepy", "almond")
BROW_STYLES = ("heavy", "thin", "arched", "low", "angry", "bushy", "short")
NOSE_STYLES = ("broad", "small", "button", "long", "hooked", "flat", "bulbous")
MOUTH_STYLES = ("wide", "full", "thin", "smile", "frown", "small", "pout")
HAIR_STYLES = (
    "bald", "crop", "mohawk", "topknot", "braids", "mane", "ponytail", "bun",
    "long", "bob", "spiky", "pigtails", "sidecut", "curly", "dreadlocks", "tonsure",
)  # fmt: skip
# Only men's bodies have beards.
BEARD_STYLES = ("none", "stubble", "full", "forked", "long", "goatee", "moustache", "chops", "short", "braided")

# The character's animations: (duration in seconds, loops). See clips.py.
CLIPS = {
    "idle": (3, True),
    "walk": (1.1, True),
    "run": (0.62, True),
    "backpedal": (0.8, True),
    "strafe_left": (0.66, True),
    "strafe_right": (0.66, True),
    "jump": (0.35, False),
    "fall": (0.8, True),
    "land": (0.3, False),
    # Fishing (clips.py): casting, waiting for a bite, reeling in (six clips the game blends by how
    # hard the line's pulled and which way the angler leans: REEL_BLEND), landing the fish, and
    # turning round to show it off.
    "fish_cast": (1.4, False),
    "fish_wait": (3, True),
    "fish_reel": (0.6, True),
    "fish_reel_left": (0.6, True),
    "fish_reel_right": (0.6, True),
    "fish_reel_hard": (0.6, True),
    "fish_reel_hard_left": (0.6, True),
    "fish_reel_hard_right": (0.6, True),
    "fish_land": (1.1, False),
    "fish_show": (3.6, False),
}
CLIP_NAMES = tuple(CLIPS)

# The clips the character has its tool in hand for (the fishing pole): it's shown only then.
TOOL_CLIPS = tuple(c for c in CLIPS if c.startswith("fish_"))

# Where the reeling clips sit for blending: (lean, strength), lean from -1 (the angler's left) to 1
# (its right), strength from 0 (reeling in slack) to 1 (hauling with all it has).
REEL_BLEND = {
    "fish_reel": (0, 0),
    "fish_reel_left": (-1, 0),
    "fish_reel_right": (1, 0),
    "fish_reel_hard": (0, 1),
    "fish_reel_hard_left": (-1, 1),
    "fish_reel_hard_right": (1, 1),
}

# The moments in a clip the game times things by, as a share of the clip: when the cast lets the
# line go, when the fish leaps out of the water and when it's caught in the left hand, and when
# it's put away after showing it off.
MARKS = {
    "fish_cast": {"release": 0.42},
    "fish_land": {"leap": 0.12, "catch": 0.6},
    "fish_show": {"stow": 0.8},
}

# The collision body's height, metres: the 48 voxels of the body.
HEIGHT = 1.8
