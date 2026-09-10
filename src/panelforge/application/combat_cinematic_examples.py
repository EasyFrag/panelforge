"""Original compact examples for Combat 1.3, adapted from the user's directing goals.

Complete Plan and Writer pairs, assembled locally from explicit teaching data.
They teach shape and causality, not a mandatory story or a rendering preset.
"""
from copy import deepcopy


def _camera(motion, target="", speed="fast", amplitude="small"):
    return {"motion": motion, "target_clause": target, "speed": speed, "amplitude": amplitude}


# Each beat supplies its cue and complete action paragraph independently. The
# maximum uses all four beats; Intense uses two longer combinations at ground level.
_EXAMPLES = {
    "powers": {
        "intention": "Eight seconds of fantasy combat: a lightning creature initially drives a fire creature backward; fire turns that pressure back. Powers are the main weapons. Two shots, mobile camera, preserve their anatomy, finish during counterfire, no music or speech.",
        "identity": "Lightning emits from the first creature's established cheek organs; fire comes from the second creature's mouth. Both retain their original bodies throughout.",
        "openings": ["A low wide view shows the lightning creature left of a split stone arch and the fire creature beyond it to the right.", "Beyond the arch, the fire creature faces the pursuing lightning creature across a shattered slab."],
        "beats": [
            ("The lightning creature springs off the slab.", "The lightning creature releases a branching volley from its cheeks across the gap. The fire creature springs sideways, sweeping a breath stream across the incoming branches; intercepted electricity bursts above the slab while a surviving bolt shears its edge. The fire creature's landing is already aimed at a second firing position."),
            ("The sheared slab tips into the gap.", "The lightning creature accelerates along the falling stone and rebounds across the gap, sending a descending fan of bolts while still airborne. The fire creature bends its sustained jet upward through the fan, then sweeps the jet across the landing route; the lightning creature changes direction off the arch before touching that route."),
            ("The fire stream reaches the arch.", "The fire creature advances behind its spreading breath, forcing the lightning creature around the broken upright. Lightning launches a low bolt along the open flank; fire twists its neck, divides the incoming line with the breath stream and drives the remaining flame into the retreat path. Broken stone falls into that path."),
            ("The broken upright starts to fall.", "Lightning rebounds from the collapsing upright in a sudden aerial reversal, firing successive bolts downward during the turn. Fire charges through the new opening with its breath rising into a broad intercepting sheet. Lightning dives past the sheet's edge and launches a concentrated discharge as fire redirects the still-active jet toward the dive.")],
        "ends": ["Fire is beyond the broken arch; lightning follows across the gap with forward momentum.", "The two attack paths are converging while both creatures are still changing position."],
        "transitions": ["Flying stone crosses the foreground; the next shot picks up fire's advance on the far side of the same arch.", "The clip ends during the converging discharge and flame, before the exchange resolves."],
        "targets": ["beside the lightning creature across the gap", "above the falling slab", "along the fire creature's advance", "below the airborne lightning creature"],
        "sound": "Electrical cracks, pressurised breath, sizzling intercepts and falling stone follow the visible attack paths. No speech.",
    },
    "heavy_weapons": {
        "intention": "Eight-second grounded axe-versus-sword duel in two mobile shots. The axe fighter drives the first combination; the swordswoman uses that commitment to reverse pressure. Heavy inertia, fast replies, unfinished last attack, no music or speech.",
        "identity": "The axe remains with the first fighter; the second keeps the sword. No supernatural strength, extra weapons or costume changes.",
        "openings": ["Low framing places the axe fighter beside a stone trough and the swordswoman at its open end.", "A side view shows both fighters travelling beyond the same chipped trough toward a timber post."],
        "beats": [
            ("The axe fighter commits his weight over the lead foot.", "The axe fighter drives a broad diagonal cleave; the swordswoman steps outside its line and guides the haft past her shoulder with the sword's strong edge. The heavy head strikes the trough, chips spraying between them. She immediately cuts toward his exposed forearm, forcing him to shorten his grip and catch her blade against the haft."),
            ("The shortened haft binds the sword.", "He thrusts the butt forward through the bind and steps across her retreat; she folds past the butt, carries her blade around the shaft and cuts on the opposite side. He turns with the axe's recovering weight and their crossing steps take both fighters past the trough, her next thrust already pursuing his turn."),
            ("The swordswoman's thrust reaches the recovering axe.", "She sends the point under the lifted haft; he knocks it outward, but the same deflection feeds her rising cut on the return. He backs toward the post under two connected changes of line, then plants his foot and drags the axe through a low sweep. She withdraws her shin and lets the sweep split the post's edge."),
            ("Splinters burst from the timber post.", "The swordswoman darts across the axe fighter's recovery, makes him turn through his own falling splinters and changes from a high feint to a committed low thrust. He answers during the turn with a short haft strike, transfers his rear hand down the shaft and drives the axe head back along her new line. Her countercut meets that return before either can reset.")],
        "ends": ["The axe fighter is turning beyond the trough; the swordswoman pursues from his outside flank.", "Both fighters carry committed weight into the next blade-and-haft contact beside the split post."],
        "transitions": ["The axe haft passes across the foreground; the next shot continues the swordswoman's pursuit beyond the trough.", "The clip ends during the countercut and returning axe, without a guard reset."],
        "targets": ["beside the axe head and the trough", "around the crossing fighters", "along the swordswoman beside the post", "toward the approaching blade and haft"],
        "sound": "Heavy air displacement, edged metal against wood, boot scrapes, stone chips and sharply timed weapon contacts. No speech.",
    },
    "aerial_fantasy": {
        "intention": "Eight seconds of aerial sword fantasy in two mobile shots. A white-robed cultivator pressures an armoured rival; the rival redirects the pursuit. Established sword-light powers, extreme travelling combinations, unfinished last strike, no music or speech.",
        "identity": "The cultivator keeps her white robes and longsword; the rival retains dark armour and a curved sword. Sword light comes from their established blades, not altered faces or anatomy.",
        "openings": ["An extreme low view shows the white-robed cultivator facing the armoured rival across the base of a ruined stair.", "Wide low framing places both rivals beyond the ruined stair beneath a broken overhead beam."],
        "beats": [
            ("The cultivator drives off the first stair.", "The cultivator flashes across the stair base with a horizontal slash; the rival slips outside the tip, redirects it upward and answers toward her ribs. She folds beneath the reply, pivots through a rising cut and carries that lift into a reverse slash. The rival's parry sends a blade-light ribbon into the stair, breaking stone as both fighters cross to its far end."),
            ("The fractured stair gives way under their passing feet.", "The cultivator rebounds from the collapsing stair, briefly suspended against the falling fragments before accelerating sharply through a descending three-line sword-light barrage. The rival runs beneath the first line, turns the second along the curved blade and springs from the wall into the third opening, already swinging upward into her descent."),
            ("The rival's rising blade reaches the descent.", "The rival catches the descending sword near its base and drives the bind sideways, forcing the cultivator past the broken beam. She changes grip during the turn, answers low then high and steps off the beam's fallen end; the rival follows the low line instead of retreating, turning her lifted arm into the opening for another thrust."),
            ("Their bound blades break apart above the beam.", "The cultivator kicks away from the beam into a rapid airborne change of direction, her sword drawing a broad crescent that descends across the rival's pursuit. The rival flashes beneath its near edge and sends a concentrated blade-light thrust up through her turn. She redirects mid-descent, robe hems stretched behind her, and drives her own point down while the upward attack is still rising.")],
        "ends": ["Both fighters have crossed beyond the broken stair; the rival is rising into the cultivator's descent.", "The opposing points and blade-light paths are closing during continued vertical travel."],
        "transitions": ["A bright blade contact crosses the foreground; the next shot inherits the same rising counter and downward momentum.", "The clip ends with the descending point and rising attack still converging."],
        "targets": ["beside the cultivator along the stair", "below the airborne rivals", "around the bound swords beside the beam", "along the descending cultivator"],
        "sound": "Blade whistles, dense metallic contacts, fractured stone, accelerating sword-light rushes and taut fabric snaps. No speech.",
    },
    "fast_weapons": {
        "intention": "Eight seconds of a grounded duel between a sabre fighter and a rapier fighter. Two mobile shots: sabre presses first, rapier redirects the pursuit. Fast connected blade work, changing heights and lines, no supernatural effects, unfinished last attack, no music or speech.",
        "identity": "The sabre and rapier stay with their original owners. Both retain their bodies and ordinary physical abilities. No blade-light powers or additional weapons.",
        "openings": ["Low three-quarter framing places the sabre fighter beside a round table and the rapier fighter across its edge.", "Wide side framing shows the rapier fighter beyond the same table and the pursuing sabre fighter entering the open aisle."],
        "beats": [
            ("The sabre fighter closes along the table edge.", "The sabre fighter cuts across the rapier fighter's upper line; the rapier guides the cut outward and returns toward the shoulder. Sabre turns the return aside, changes level into a low sweeping cut and follows the rapier fighter's withdrawing leg. Rapier steps around the table corner and directs a short reply into the space opened by the low cut."),
            ("The short reply reaches the sabre fighter's passing shoulder.", "Sabre rotates through the near miss and carries the recovery into a rising cut; rapier beats the rising blade outward, passes close on the opposite side and snaps the point back toward the exposed flank. Sabre shortens the return, catches the point against the stronger blade section and pursues the resulting turn beyond the table, both fighters accelerating through the crossing pass."),
            ("The rapier fighter turns beyond the table.", "Rapier yields half a step then sends a straight thrust through sabre's recovering line. Sabre turns it down, but rapier circles the tip around the parry and renews toward the other shoulder. Sabre slips past the second thrust, slices across the open wrist line and forces rapier to rotate the grip while travelling backward along the aisle."),
            ("The rotating grip brings the rapier point back inside.", "Rapier bursts forward under sabre's high feint, changing the thrust from chest to hip as sabre steps across its line. Sabre answers during the passing step with a turning back-cut; rapier folds past its tip, plants the rear foot and launches a renewed thrust before sabre's turn finishes. Sabre drives the blade back across the renewed point and both close through the counter.")],
        "ends": ["Both fighters are beyond the table; sabre pursues rapier's turn into the open aisle.", "The renewed point and returning sabre converge while the fighters are still closing."],
        "transitions": ["The passing blades briefly fill the foreground; the next shot continues the rapier fighter's turn beyond the same table.", "The clip ends during the renewed thrust and returning cut, without a guard reset."],
        "targets": ["beside the sabre along the table edge", "around the crossing fighters beyond the table", "along the rapier fighter through the aisle", "beside the approaching blade tips"],
        "sound": "Rapid blade whistles, crisp blade contacts, boot pivots and fabric snaps follow the changing lines of attack. No speech.",
    },
    "hand_to_hand": {
        "intention": "Eight-second grounded hand-to-hand encounter in two mobile shots. A red-jacket fighter initially pressures a blue-jacket fighter, who reverses the pursuit. Varied footwork, continuous combinations, unfinished counter, no music or speech.",
        "identity": "Red and blue keep their faces, jackets and ordinary human abilities. No weapons, magical effects or extra opponents.",
        "openings": ["Low wide framing places red on the left and blue on the right beside a bench.", "A side view shows blue beyond the same bench with red pursuing from the aisle."],
        "beats": [
            ("Red steps across the open aisle.", "Red drives a straight punch that blue slips outside; red carries that extension into a short elbow as blue checks the forearm and turns the collision into a body counter. Red absorbs the reply while stepping through, hooks blue's checking wrist and uses the grip to drive blue around the bench."),
            ("Blue's heel reaches the bench leg.", "Blue vaults the low end of the bench while pulling the captured wrist free, landing into an immediate straight counter. Red redirects it, crosses to blue's outside and follows with a turning kick. Blue ducks under the kick and attacks red's supporting leg during its recovery, forcing both fighters into the narrow aisle beyond the bench."),
            ("Red's supporting foot skids into the aisle.", "Blue presses the lost footing with a shoulder entry; red pivots along the bench edge and tries to turn that entry into a throw. Blue widens the base, carries the attempted turn past red's hip and strikes through the resulting opening. Red catches the wrist and steps across to prevent the next body blow."),
            ("The captured wrist draws blue into the turn.", "Blue rolls the grip outward, changes level beneath red's arm and rebounds into a rising counter. Red sidesteps across blue's forward line, meets the counter at the forearm and drives a returning elbow while blue's free hand is already striking toward red's ribs. Both attacks continue as their feet cross the end of the aisle.")],
        "ends": ["Blue is established beyond the bench; red is recovering forward into the aisle.", "Both fighters are committed to simultaneous replies at the end of the aisle."],
        "transitions": ["Red's jacket sweeps across the foreground; the next shot continues blue's pressure from the same side of the bench.", "The clip ends during the elbow and body counter, before either fighter returns to guard."],
        "targets": ["beside the fighters across the aisle", "around the fighters at the bench", "along blue beyond the bench", "beside the crossing forearms"],
        "sound": "Foot skids, fabric tension, breath and body-contact thuds grounded in each visible exchange. No speech.",
    },
}


def example(key, *, unleashed):
    data = deepcopy(_EXAMPLES[key])
    shots, written = [], []
    for index in range(2):
        indexes = [index * 2, index * 2 + 1] if unleashed else [index * 2]
        phases = []
        for offset, beat_index in enumerate(indexes):
            cue, action = data["beats"][beat_index]
            motion = "tracking_shot" if offset == 0 else "pedestal.up" if key in {"powers", "aerial_fantasy"} else "arc_shot"
            phases.append({"cue": cue, "camera": _camera(motion, data["targets"][beat_index], amplitude="large" if unleashed else "small"), "exchanges": [action]})
        shots.append({"duration_ms": 4000, "opening_composition": data["openings"][index], "phases": phases,
            "pacing": "Brief impact resistance gives way to an explosive acceleration through a larger traversal." if unleashed else "Linked actions sustain pressure through rapid re-entry and a clear change of initiative.",
            "end_state": data["ends"][index], "transition": data["transitions"][index]})
        if not unleashed and key == "aerial_fantasy" and index == 0:
            shots[-1]["end_state"] = "Both fighters have crossed the broken stair; the rival begins a rising counter as the cultivator turns into a descending reply."
        written.append({"phases": [" ".join(p["exchanges"]) for p in phases]})
    audio = {"overall_soundscape": data["sound"], "non_diegetic_music": "N/A"}
    return {"intention": data["intention"] + (" Action: Unleashed." if unleashed else " Action: Intense."),
        "plan": {"continuity_invariants": [data["identity"]], "shots": shots, "spoken_lines": [], **audio},
        "writer": {"shots": written, **audio}}
