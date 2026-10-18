"""
A body's proportions: where its joints and landmarks are, how wide and deep each part is, the
ears' shape, where the face goes, and what its race adds to the head. The body, the rig, the clips
and every item of gear are built from these, so a new body is a new `Race` here and nothing else.

All of it is in voxels, y up from the soles, the character facing +z with its left at +x. Heights
are rows (a cell at row y spans y..y+1); widths are out from the middle. A voxel is the same size
for every body (rig.VOXEL), so a taller race is taller in metres too.

What stays the same across bodies: the 20 bones and their names (defs.BONES), so every clip and the
gear system work on any body; the faces' columns (eyes 2–4 out, nose and mouth in the middle) and
their rows relative to each other (the nose three below the eyes, the mouth one below the nose), so
a head should stay about 18 wide; and the gear's depths (how far out from the body each piece is).

Every race has a male and a female body (`BODIES`, named `<race>_<sex>`). Women are slighter: a
narrower chest and shoulders, slimmer arms and legs, smaller hands and feet, and wider hips, with a
bust; the game draws them a little shorter too.

  human   48 tall, the head two fifths of it, stocky and short in the leg (the original body)
  dwarf   40 tall and nearly as wide: a barrel chest and belly, thick arms, short heavy legs
  elf     56 tall and slim, long in the leg, the head under a third of it, ears long and swept back
  gnome   32 tall, half of it head: a tiny body, big ears sticking out to the sides
  orc     52 tall, broad and muscled, the head thrust forward, a jutting jaw with tusks
  ogre    66 tall, huge: a great gut, massive arms, a small head hunched low, big tusks
  undead  47 tall, gaunt: thin limbs, a sunken belly, hollow eyes, rot and bare bone
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Race:
    name: str
    # The whole height, to the top of the hair: the collision body.
    height: int

    # --- Heights (rows, y up from the soles) ----------------------------------------------------
    # The legs: the foot from the sole to the ankle, the shin to the knee, the thigh to the hip.
    sole: int
    ankle: int
    knee: int
    hip: int
    # The hips' joint, and the belt's lower row (it's two rows deep).
    belt: int
    # Where the hips end and the belly (the spine bone) begins; the shirt's hem.
    waist: int
    # The middle of the belly's barrel.
    belly: float
    # The chest bone's joint, below the shoulders.
    chest: int
    # The arms: the shoulder joint, the elbow, the wrist (the hand hangs below it).
    shoulder: int
    elbow: int
    wrist: int
    # The neck's joint, and the skull from its bottom (where the head bone takes over) to its top.
    neck: int
    head_bottom: int
    head_top: int

    # --- Out from the middle ---------------------------------------------------------------------
    # The legs' middle.
    leg_x: float
    # Where the arms begin (anything this far out below the head moves with an arm), and their middle.
    arm_in: int
    arm_x: float
    # How far back of the middle the hips and legs sit (z).
    leg_z: float

    # --- Sizes: half-widths (x), half-heights (y) and half-depths (z), and roundings -----------
    # The torso: a rounded box from the waist to the head, and a barrel of a belly over it.
    torso_half: tuple  # (x, z)
    torso_round: float
    belly_radii: tuple  # (x, y, z)
    belly_z: float
    # The neck, centred on the head's bottom.
    neck_half: tuple  # (x, y, z)
    neck_round: float
    # The hips, centred on the belt.
    hips_half: tuple  # (x, y, z)
    hips_round: float
    # The legs: the thigh's bulk and the shin, each from joint to joint.
    thigh_half: tuple  # (x, z)
    thigh_round: float
    shin_half: tuple  # (x, z)
    shin_round: float
    # The foot from the sole to the ankle, and a sole under it, both centred `_z` forward.
    foot_half: tuple  # (x, z)
    foot_z: float
    foot_round: float
    sole_half: tuple  # (x, z)
    sole_z: float
    sole_round: float
    # The upper arm from the elbow to the neck, and the shoulder's muscle, placed (x, y) from
    # (arm_x, shoulder).
    upper_arm_half: tuple  # (x, z)
    upper_arm_round: float
    deltoid_radii: tuple  # (x, y, z)
    deltoid_at: tuple  # (x, y)
    # The forearm from the wrist to the elbow.
    forearm_half: tuple  # (x, z)
    forearm_z: float
    forearm_round: float
    # The fist and the thumb, placed (x, y, z) from (arm_x, wrist).
    fist_half: tuple  # (x, y, z)
    fist_at: tuple
    fist_round: float
    thumb_half: tuple  # (x, y, z)
    thumb_at: tuple
    thumb_round: float
    # The skull, from head_bottom to head_top, centred `head_z` forward.
    head_half: tuple  # (x, z)
    head_z: float
    head_round: float

    # --- Ears ------------------------------------------------------------------------------------
    # Two capsules each, placed (out, up, forward) from the side of the skull at the eyes' row: the
    # ear from its root to its tip, and the lobe. `ear_fold` is how many rows the darker fold inside
    # runs up from the eyes' row.
    ear_root: tuple
    ear_tip: tuple
    ear_radius: float
    lobe: tuple
    lobe_end: tuple
    lobe_radius: float
    ear_fold: int

    # --- The face ------------------------------------------------------------------------------
    # The eyes' bottom row (the lid is two above, the brows three and four), the nose's bottom row
    # and the mouth's row.
    eye_row: int
    nose_row: int
    mouth_row: int

    # --- What the race adds --------------------------------------------------------------------
    # The race it is and which of its bodies (the name is `<race>_<sex>`).
    race: str = "human"
    sex: str = "male"
    # A bust: each breast's radii (x, y, z), placed (out, row, forward) from the middle; None for none.
    bust: tuple | None = None
    bust_at: tuple = (0, 0, 0)
    # The torso's half-width below the chest, if it's narrower there than above (a woman's waist).
    waist_half: float = 0
    # Tusks jutting up from the lower jaw: 0 none, 1 an orc's, 2 an ogre's great ones.
    tusks: int = 0
    # How far the lower jaw juts out past the lip (an underbite), in voxels.
    jaw: int = 0
    # Dark sockets where the whites of the eyes would be (the iris glows in the game).
    hollow_eyes: bool = False
    # Rot: blotched skin, bare bone at the cheek and forearm, a ragged shirt.
    decay: bool = False

    # --- Landmarks worked out from the rest ------------------------------------------------------

    @property
    def front(self) -> int:
        """The face's front: the last layer of the skull's cells (features stand a voxel or two proud of it)."""
        return math.ceil(self.head_z + self.head_half[1]) - 1

    @property
    def back(self) -> float:
        """The back of the skull (z)."""
        return self.head_z - self.head_half[1]

    @property
    def chest_front(self) -> int:
        """Where a pendant hangs on the chest (z): the second layer out from the torso's front."""
        front = max(self.torso_half[1], self.belly_z + self.belly_radii[2])
        if self.bust:
            front = max(front, self.bust_at[2] + self.bust[2])
        surface = math.floor(front - 0.5) + 1
        return surface + 1

    @property
    def shoulder_cap(self) -> int:
        """The bottom of the shoulder bone's bit of the arm."""
        return self.shoulder - 3

    @property
    def arm_top(self) -> float:
        """The crown of the shoulder: on a brawny body it rises past the bottom of the head."""
        return self.shoulder + self.deltoid_at[1] + self.deltoid_radii[1]

    @property
    def sleeve(self) -> int:
        """The shirt's short sleeves' hem."""
        return self.elbow + 2

    def down_thigh(self, t: float) -> float:
        """The row `t` of the way down the thigh from the hip to the knee: where a skirt's hem goes."""
        return self.hip - (self.hip - self.knee) * t

    def check(self) -> "Race":
        """Raises if the landmarks are out of order or the head's off the top."""
        order = ("sole", "ankle", "knee", "hip", "waist", "chest", "shoulder", "neck", "head_bottom", "head_top")
        for a, b in zip(order, order[1:]):
            if not getattr(self, a) < getattr(self, b):
                raise ValueError(f"{self.name}: {a} ({getattr(self, a)}) must be below {b} ({getattr(self, b)})")
        for a, b in (("wrist", "elbow"), ("elbow", "shoulder"), ("hip", "belt"), ("belt", "waist")):
            if not getattr(self, a) < getattr(self, b):
                raise ValueError(f"{self.name}: {a} must be below {b}")
        if self.head_top >= self.height:
            raise ValueError(f"{self.name}: head_top must be below the height")
        if not (self.nose_row == self.mouth_row + 1 and self.eye_row == self.nose_row + 3):
            raise ValueError(f"{self.name}: the nose goes one row over the mouth, the eyes three over the nose")
        if self.name != f"{self.race}_{self.sex}":
            raise ValueError(f"{self.name}: a body is named <race>_<sex>")
        if not self.leg_x < self.arm_in <= self.arm_x:
            raise ValueError(f"{self.name}: the legs must be inside the arms")
        return self




# --- Humans ---------------------------------------------------------------------------------------

HUMAN = Race(
    name="human_male",
    height=48,
    sole=0,
    ankle=4,
    knee=8,
    hip=13,
    belt=15,
    waist=17,
    belly=21.5,
    chest=22,
    shoulder=27,
    elbow=21,
    wrist=15,
    neck=29,
    head_bottom=30,
    head_top=47,
    leg_x=3.5,
    arm_in=8,
    arm_x=11.5,
    leg_z=-0.5,
    torso_half=(8, 5),
    torso_round=3.2,
    belly_radii=(8.3, 6.2, 5.8),
    belly_z=0.6,
    neck_half=(3.5, 2, 3.5),
    neck_round=1,
    hips_half=(7.2, 2.5, 4.6),
    hips_round=1.6,
    thigh_half=(3, 3),
    thigh_round=1.4,
    shin_half=(2.6, 2.6),
    shin_round=1,
    foot_half=(3, 4.2),
    foot_z=0.9,
    foot_round=1.2,
    sole_half=(3, 4.3),
    sole_z=1,
    sole_round=0.4,
    upper_arm_half=(2.6, 2.6),
    upper_arm_round=1.2,
    deltoid_radii=(3.4, 2.7, 3),
    deltoid_at=(-0.9, 0.4),
    forearm_half=(2.5, 2.2),
    forearm_z=0.3,
    forearm_round=1,
    fist_half=(3, 2.9, 3),
    fist_at=(0, -2.6, 0.5),
    fist_round=1,
    thumb_half=(1, 1.4, 1),
    thumb_at=(-2.1, -1.8, 2.8),
    thumb_round=0.4,
    head_half=(9, 8.5),
    head_z=0.5,
    head_round=3.6,
    ear_root=(0.4, 0.5, 1),
    ear_tip=(3.4, 4.8, -0.6),
    ear_radius=1.25,
    lobe=(0.4, 0, 1.2),
    lobe_end=(1.2, 0, 0.8),
    lobe_radius=1.3,
    ear_fold=3,
    eye_row=35,
    nose_row=32,
    mouth_row=31,
).check()

HUMAN_F = replace(
    HUMAN,
    name="human_female",
    sex="female",
    arm_in=8,
    arm_x=10.6,
    torso_half=(7, 4.4),
    torso_round=3,
    belly_radii=(5.6, 5, 4.4),
    belly_z=0.3,
    neck_half=(2.8, 2, 2.9),
    hips_half=(7.6, 3, 5),
    thigh_half=(3.1, 3),
    shin_half=(2.3, 2.3),
    foot_half=(2.5, 3.7),
    foot_z=0.8,
    sole_half=(2.5, 3.8),
    upper_arm_half=(2.1, 2.1),
    deltoid_radii=(2.6, 2.2, 2.4),
    deltoid_at=(-0.6, 0.3),
    forearm_half=(2, 1.8),
    fist_half=(2.4, 2.5, 2.5),
    fist_at=(0, -2.3, 0.4),
    thumb_half=(0.9, 1.2, 0.9),
    thumb_at=(-1.7, -1.6, 2.3),
    bust=(3, 2.6, 2.7),
    bust_at=(3.3, 25, 3.6),
    waist_half=5.6,
).check()

# --- Dwarves --------------------------------------------------------------------------------------

DWARF = Race(
    name="dwarf_male",
    race="dwarf",
    height=40,
    sole=0,
    ankle=3,
    knee=6,
    hip=10,
    belt=12,
    waist=14,
    belly=16.5,
    chest=17,
    shoulder=20,
    elbow=15,
    wrist=10,
    neck=21,
    head_bottom=22,
    head_top=39,
    leg_x=4.4,
    arm_in=10,
    arm_x=13.8,
    leg_z=-0.5,
    torso_half=(10, 6),
    torso_round=3.6,
    belly_radii=(10, 5.6, 6.8),
    belly_z=1,
    neck_half=(4.6, 1.5, 4.2),
    neck_round=1,
    hips_half=(9, 2.4, 5.4),
    hips_round=1.8,
    thigh_half=(3.6, 3.5),
    thigh_round=1.4,
    shin_half=(3.2, 3.1),
    shin_round=1.1,
    foot_half=(3.6, 4.7),
    foot_z=1,
    foot_round=1.3,
    sole_half=(3.6, 4.8),
    sole_z=1.1,
    sole_round=0.4,
    upper_arm_half=(3.2, 3.1),
    upper_arm_round=1.3,
    deltoid_radii=(4, 3, 3.6),
    deltoid_at=(-0.9, 0.2),
    forearm_half=(3.1, 2.8),
    forearm_z=0.3,
    forearm_round=1.1,
    fist_half=(3.4, 3, 3.4),
    fist_at=(0, -2.5, 0.5),
    fist_round=1,
    thumb_half=(1.1, 1.4, 1.1),
    thumb_at=(-2.4, -1.8, 3.1),
    thumb_round=0.4,
    head_half=(9, 8.5),
    head_z=0.8,
    head_round=3.6,
    ear_root=(0.4, 0.5, 1),
    ear_tip=(3.2, 3.8, -0.4),
    ear_radius=1.35,
    lobe=(0.4, 0, 1.2),
    lobe_end=(1.4, -0.4, 0.8),
    lobe_radius=1.5,
    ear_fold=3,
    eye_row=27,
    nose_row=24,
    mouth_row=23,
).check()

DWARF_F = replace(
    DWARF,
    name="dwarf_female",
    sex="female",
    arm_in=10,
    arm_x=13,
    torso_half=(9, 5.4),
    torso_round=3.4,
    belly_radii=(7.4, 4.8, 5.4),
    belly_z=0.6,
    neck_half=(3.8, 1.5, 3.6),
    hips_half=(9.6, 2.8, 5.8),
    thigh_half=(3.6, 3.4),
    shin_half=(2.9, 2.8),
    foot_half=(3.1, 4.2),
    sole_half=(3.1, 4.3),
    upper_arm_half=(2.7, 2.6),
    deltoid_radii=(3.3, 2.5, 3),
    deltoid_at=(-0.7, 0.2),
    forearm_half=(2.6, 2.4),
    fist_half=(2.9, 2.7, 2.9),
    fist_at=(0, -2.3, 0.5),
    thumb_half=(1, 1.3, 1),
    thumb_at=(-2, -1.6, 2.7),
    bust=(3.5, 2.8, 2.9),
    bust_at=(3.9, 18.2, 4.6),
    waist_half=7.4,
).check()

# --- Elves ----------------------------------------------------------------------------------------

ELF = Race(
    name="elf_male",
    race="elf",
    height=56,
    sole=0,
    ankle=4,
    knee=12,
    hip=21,
    belt=23,
    waist=25,
    belly=29.5,
    chest=30,
    shoulder=35,
    elbow=28,
    wrist=21,
    neck=38,
    head_bottom=39,
    head_top=55,
    leg_x=3,
    arm_in=7,
    arm_x=9.5,
    leg_z=-0.5,
    torso_half=(7, 4),
    torso_round=2.8,
    belly_radii=(6.8, 6, 4.4),
    belly_z=0.3,
    neck_half=(2.5, 2, 2.5),
    neck_round=1,
    hips_half=(6, 2.5, 3.8),
    hips_round=1.4,
    thigh_half=(2.4, 2.4),
    thigh_round=1.2,
    shin_half=(2, 2),
    shin_round=0.9,
    foot_half=(2.2, 3.6),
    foot_z=0.9,
    foot_round=1,
    sole_half=(2.2, 3.7),
    sole_z=1,
    sole_round=0.4,
    upper_arm_half=(2, 2),
    upper_arm_round=1,
    deltoid_radii=(2.6, 2.2, 2.4),
    deltoid_at=(-0.6, 0.4),
    forearm_half=(1.9, 1.8),
    forearm_z=0.3,
    forearm_round=0.9,
    fist_half=(2.3, 2.6, 2.4),
    fist_at=(0, -2.4, 0.5),
    fist_round=0.9,
    thumb_half=(0.9, 1.3, 0.9),
    thumb_at=(-1.6, -1.6, 2.4),
    thumb_round=0.4,
    head_half=(8.5, 8),
    head_z=0.5,
    head_round=3.4,
    # Long and swept up and back.
    ear_root=(0.4, 0.5, 0.8),
    ear_tip=(4.6, 7.5, -3),
    ear_radius=1.1,
    lobe=(0.4, 0, 1),
    lobe_end=(1, 0, 0.7),
    lobe_radius=1.1,
    ear_fold=5,
    eye_row=44,
    nose_row=41,
    mouth_row=40,
).check()

ELF_F = replace(
    ELF,
    name="elf_female",
    sex="female",
    arm_in=7,
    arm_x=9,
    torso_half=(6, 3.6),
    torso_round=2.6,
    belly_radii=(4.8, 5, 3.4),
    belly_z=0.2,
    neck_half=(2.2, 2, 2.2),
    hips_half=(6.8, 2.8, 4.1),
    thigh_half=(2.5, 2.4),
    shin_half=(1.8, 1.8),
    foot_half=(1.9, 3.2),
    sole_half=(1.9, 3.3),
    upper_arm_half=(1.7, 1.7),
    deltoid_radii=(2.1, 1.9, 2),
    deltoid_at=(-0.4, 0.3),
    forearm_half=(1.6, 1.5),
    fist_half=(1.9, 2.2, 2),
    fist_at=(0, -2.1, 0.4),
    thumb_half=(0.8, 1.1, 0.8),
    thumb_at=(-1.3, -1.4, 2),
    bust=(2.5, 2.3, 2.3),
    bust_at=(2.8, 32.5, 3),
    waist_half=4.8,
).check()

# --- Gnomes ---------------------------------------------------------------------------------------

GNOME = Race(
    name="gnome_male",
    race="gnome",
    height=32,
    sole=0,
    ankle=2,
    knee=4,
    hip=6,
    belt=7,
    waist=8,
    belly=10,
    chest=11,
    shoulder=13,
    elbow=10,
    wrist=7,
    neck=14,
    head_bottom=15,
    head_top=31,
    leg_x=2.6,
    arm_in=6,
    arm_x=8.3,
    leg_z=-0.4,
    torso_half=(6, 4.2),
    torso_round=2.6,
    belly_radii=(6.2, 3.6, 4.8),
    belly_z=0.6,
    neck_half=(2.8, 1, 2.8),
    neck_round=0.8,
    hips_half=(5.6, 1.6, 3.8),
    hips_round=1.2,
    thigh_half=(2.4, 2.4),
    thigh_round=1.1,
    shin_half=(2.1, 2.1),
    shin_round=0.9,
    foot_half=(2.5, 3.6),
    foot_z=1.1,
    foot_round=1,
    sole_half=(2.5, 3.7),
    sole_z=1.2,
    sole_round=0.4,
    upper_arm_half=(2, 2),
    upper_arm_round=1,
    deltoid_radii=(2.4, 1.8, 2.2),
    deltoid_at=(-0.5, 0.2),
    forearm_half=(1.9, 1.8),
    forearm_z=0.3,
    forearm_round=0.9,
    fist_half=(2.3, 2, 2.3),
    fist_at=(0, -1.6, 0.4),
    fist_round=0.9,
    thumb_half=(0.8, 1, 0.8),
    thumb_at=(-1.6, -1.2, 2.1),
    thumb_round=0.4,
    head_half=(9, 8.5),
    head_z=0.4,
    head_round=4,
    # Big, and out to the sides.
    ear_root=(0.3, 0.3, 0.6),
    ear_tip=(6.2, 3.2, -1.6),
    ear_radius=1.5,
    lobe=(0.3, -0.5, 0.8),
    lobe_end=(2.2, -0.6, 0.2),
    lobe_radius=1.5,
    ear_fold=3,
    eye_row=20,
    nose_row=17,
    mouth_row=16,
).check()

GNOME_F = replace(
    GNOME,
    name="gnome_female",
    sex="female",
    arm_in=6,
    arm_x=8,
    torso_half=(5.2, 3.8),
    torso_round=2.4,
    belly_radii=(4.4, 3, 3.7),
    belly_z=0.3,
    neck_half=(2.3, 1, 2.3),
    hips_half=(5.8, 1.8, 4),
    thigh_half=(2.4, 2.3),
    shin_half=(1.8, 1.8),
    foot_half=(2.1, 3.2),
    sole_half=(2.1, 3.3),
    upper_arm_half=(1.7, 1.7),
    deltoid_radii=(2, 1.6, 1.9),
    deltoid_at=(-0.4, 0.2),
    forearm_half=(1.6, 1.5),
    fist_half=(1.9, 1.8, 2),
    fist_at=(0, -1.5, 0.4),
    thumb_half=(0.7, 0.9, 0.7),
    thumb_at=(-1.3, -1.1, 1.8),
    bust=(2.1, 1.7, 1.9),
    bust_at=(2.3, 11.7, 3.2),
    waist_half=4.4,
).check()

# --- Orcs -----------------------------------------------------------------------------------------

ORC = Race(
    name="orc_male",
    race="orc",
    height=52,
    sole=0,
    ankle=4,
    knee=9,
    hip=15,
    belt=17,
    waist=19,
    belly=23.5,
    chest=24,
    shoulder=30,
    elbow=23,
    wrist=16,
    neck=32,
    head_bottom=33,
    head_top=50,
    leg_x=4.2,
    arm_in=10,
    arm_x=14.2,
    leg_z=-0.5,
    torso_half=(10, 6),
    torso_round=3.4,
    belly_radii=(9.4, 6.2, 6.2),
    belly_z=0.4,
    neck_half=(5, 2, 4.4),
    neck_round=1.2,
    hips_half=(8.2, 2.5, 5),
    hips_round=1.6,
    thigh_half=(3.6, 3.5),
    thigh_round=1.4,
    shin_half=(3.1, 3),
    shin_round=1.1,
    foot_half=(3.4, 4.7),
    foot_z=1,
    foot_round=1.2,
    sole_half=(3.4, 4.8),
    sole_z=1.1,
    sole_round=0.4,
    upper_arm_half=(3.4, 3.3),
    upper_arm_round=1.3,
    deltoid_radii=(4.8, 3.6, 4.2),
    deltoid_at=(-0.7, 0.8),
    forearm_half=(3.3, 3),
    forearm_z=0.4,
    forearm_round=1.1,
    fist_half=(3.6, 3.3, 3.6),
    fist_at=(0, -2.8, 0.6),
    fist_round=1.1,
    thumb_half=(1.2, 1.6, 1.2),
    thumb_at=(-2.5, -2, 3.3),
    thumb_round=0.4,
    head_half=(9, 8.5),
    head_z=1.8,
    head_round=3.4,
    # Pointed, cocked back.
    ear_root=(0.4, 0.4, 0.8),
    ear_tip=(3.8, 3.4, -2.6),
    ear_radius=1.2,
    lobe=(0.4, 0, 1),
    lobe_end=(1.1, -0.2, 0.7),
    lobe_radius=1.2,
    ear_fold=3,
    eye_row=38,
    nose_row=35,
    mouth_row=34,
    tusks=1,
    jaw=1,
).check()

ORC_F = replace(
    ORC,
    name="orc_female",
    sex="female",
    arm_in=10,
    arm_x=12.8,
    torso_half=(8, 5.2),
    torso_round=3.2,
    belly_radii=(6.6, 5.2, 4.8),
    belly_z=0.3,
    neck_half=(3.6, 2, 3.4),
    hips_half=(9.4, 2.9, 5.4),
    thigh_half=(3.5, 3.3),
    shin_half=(2.7, 2.6),
    foot_half=(2.9, 4.1),
    sole_half=(2.9, 4.2),
    upper_arm_half=(2.7, 2.6),
    deltoid_radii=(3.5, 2.7, 3.1),
    deltoid_at=(-0.6, 0.5),
    forearm_half=(2.6, 2.4),
    fist_half=(2.9, 2.8, 2.9),
    fist_at=(0, -2.5, 0.5),
    thumb_half=(1, 1.3, 1),
    thumb_at=(-2, -1.8, 2.7),
    bust=(3.4, 2.8, 2.9),
    bust_at=(3.8, 27, 4.4),
    waist_half=6.6,
).check()

# --- Ogres ----------------------------------------------------------------------------------------

OGRE = Race(
    name="ogre_male",
    race="ogre",
    height=66,
    sole=0,
    ankle=5,
    knee=13,
    hip=21,
    belt=23,
    waist=25,
    belly=32,
    chest=33,
    shoulder=44,
    elbow=33,
    wrist=23,
    neck=47,
    head_bottom=48,
    head_top=65,
    leg_x=6.4,
    arm_in=14,
    arm_x=19.6,
    leg_z=-0.5,
    torso_half=(14, 8.4),
    torso_round=4.6,
    belly_radii=(14.2, 9.6, 9),
    belly_z=2,
    neck_half=(6.4, 2, 5.6),
    neck_round=1.6,
    hips_half=(12.6, 3, 7.4),
    hips_round=2.2,
    thigh_half=(5.4, 5.2),
    thigh_round=2,
    shin_half=(4.6, 4.4),
    shin_round=1.6,
    foot_half=(5, 6),
    foot_z=1.4,
    foot_round=1.6,
    sole_half=(5, 6.1),
    sole_z=1.5,
    sole_round=0.5,
    upper_arm_half=(4.8, 4.6),
    upper_arm_round=1.8,
    deltoid_radii=(6.2, 4.8, 5.4),
    deltoid_at=(-1, 0.8),
    forearm_half=(4.8, 4.4),
    forearm_z=0.5,
    forearm_round=1.6,
    fist_half=(5.4, 4.6, 5.2),
    fist_at=(0, -3.8, 0.8),
    fist_round=1.4,
    thumb_half=(1.8, 2.2, 1.8),
    thumb_at=(-3.6, -2.8, 4.4),
    thumb_round=0.6,
    head_half=(9, 8.5),
    head_z=3,
    head_round=3.8,
    # Small and stuck to the skull.
    ear_root=(0.3, 0, 0.6),
    ear_tip=(1.9, 1.4, -0.6),
    ear_radius=1.6,
    lobe=(0.3, -1, 0.8),
    lobe_end=(1.1, -1.6, 0.4),
    lobe_radius=1.4,
    ear_fold=2,
    eye_row=53,
    nose_row=50,
    mouth_row=49,
    tusks=2,
    jaw=2,
).check()

OGRE_F = replace(
    OGRE,
    name="ogre_female",
    sex="female",
    arm_in=14,
    arm_x=18.4,
    torso_half=(12, 7.6),
    torso_round=4.4,
    belly_radii=(10.6, 8.5, 7.6),
    belly_z=1.4,
    neck_half=(5.4, 2, 5),
    hips_half=(13.4, 3.4, 8),
    thigh_half=(5.2, 5),
    shin_half=(4.1, 4),
    foot_half=(4.4, 5.4),
    sole_half=(4.4, 5.5),
    upper_arm_half=(4, 3.9),
    deltoid_radii=(5.2, 4, 4.6),
    deltoid_at=(-0.8, 0.6),
    forearm_half=(4, 3.7),
    fist_half=(4.6, 4, 4.5),
    fist_at=(0, -3.4, 0.7),
    thumb_half=(1.6, 2, 1.6),
    thumb_at=(-3.1, -2.5, 3.9),
    bust=(4.8, 4, 4.1),
    bust_at=(5.2, 38.5, 7),
    waist_half=10.4,
).check()

# --- The undead -----------------------------------------------------------------------------------

UNDEAD = Race(
    name="undead_male",
    race="undead",
    height=47,
    sole=0,
    ankle=4,
    knee=8,
    hip=13,
    belt=15,
    waist=17,
    belly=21.5,
    chest=22,
    shoulder=27,
    elbow=21,
    wrist=15,
    neck=29,
    head_bottom=30,
    head_top=46,
    leg_x=3.2,
    arm_in=7,
    arm_x=9.7,
    leg_z=-0.5,
    torso_half=(6.8, 4.2),
    torso_round=2.6,
    belly_radii=(6, 5, 3.4),
    belly_z=-0.2,
    neck_half=(2.3, 2, 2.3),
    neck_round=0.8,
    hips_half=(6.2, 2.4, 4),
    hips_round=1.4,
    thigh_half=(2.2, 2.2),
    thigh_round=1,
    shin_half=(1.9, 1.9),
    shin_round=0.8,
    foot_half=(2.6, 4),
    foot_z=0.9,
    foot_round=1,
    sole_half=(2.6, 4.1),
    sole_z=1,
    sole_round=0.4,
    upper_arm_half=(1.8, 1.8),
    upper_arm_round=0.8,
    deltoid_radii=(2.5, 2.2, 2.4),
    deltoid_at=(-0.5, 0.4),
    forearm_half=(1.7, 1.6),
    forearm_z=0.3,
    forearm_round=0.7,
    fist_half=(2.4, 2.7, 2.6),
    fist_at=(0, -2.5, 0.5),
    fist_round=0.8,
    thumb_half=(0.8, 1.2, 0.8),
    thumb_at=(-1.6, -1.7, 2.3),
    thumb_round=0.4,
    head_half=(8.5, 8),
    head_z=0.9,
    head_round=3.2,
    ear_root=(0.4, 0.5, 0.9),
    ear_tip=(2.8, 4, -0.8),
    ear_radius=1.1,
    lobe=(0.4, 0, 1.1),
    lobe_end=(1, 0, 0.8),
    lobe_radius=1.1,
    ear_fold=3,
    eye_row=35,
    nose_row=32,
    mouth_row=31,
    hollow_eyes=True,
    decay=True,
).check()

UNDEAD_F = replace(
    UNDEAD,
    name="undead_female",
    sex="female",
    arm_in=7,
    arm_x=9,
    torso_half=(6, 3.8),
    torso_round=2.4,
    belly_radii=(4.8, 4.6, 3),
    neck_half=(2.1, 2, 2.1),
    hips_half=(6.8, 2.7, 4.3),
    thigh_half=(2.3, 2.2),
    shin_half=(1.7, 1.7),
    foot_half=(2.2, 3.6),
    sole_half=(2.2, 3.7),
    upper_arm_half=(1.6, 1.6),
    deltoid_radii=(2.1, 1.9, 2),
    deltoid_at=(-0.4, 0.3),
    forearm_half=(1.5, 1.4),
    fist_half=(2, 2.3, 2.2),
    fist_at=(0, -2.2, 0.4),
    thumb_half=(0.7, 1.1, 0.7),
    thumb_at=(-1.3, -1.5, 2),
    bust=(2.3, 2.1, 2),
    bust_at=(2.7, 25, 3.1),
    waist_half=4.8,
).check()

# Every body, the default first: `<race>_<sex>`.
BODIES = {
    r.name: r
    for r in (HUMAN, HUMAN_F, DWARF, DWARF_F, ELF, ELF_F, GNOME, GNOME_F, ORC, ORC_F, OGRE, OGRE_F, UNDEAD, UNDEAD_F)
}
RACES = tuple(dict.fromkeys(r.race for r in BODIES.values()))
DEFAULT = HUMAN

# The body being built: the body, the rig, the clips and the gear all ask for it. build.py sets it.
_current = DEFAULT


def use(body: Race | str) -> Race:
    """Builds everything from here on for `body` (a Race or its name)."""
    global _current
    _current = (BODIES[body] if isinstance(body, str) else body).check()
    return _current


def current() -> Race:
    return _current


# `replace(HUMAN, name="...", ...)` makes a variant of a body.
__all__ = ["BODIES", "DEFAULT", "RACES", "Race", "current", "replace", "use"]
