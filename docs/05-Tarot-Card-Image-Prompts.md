# Tarot Card Image Prompts

## 1. Scope

- Current project has two tarot layers that should not be mixed:
- Runtime deck: `agent/core/tarot_deck.py` defines a full 78-card Rider-Waite-Smith style deck used by the backend draw flow.
- Frontend mock catalog: `frontend/src/data/tarotCatalog.ts` currently hardcodes 10 sample cards for local UI preview only.
- This document targets the real runtime deck of 78 cards so the image asset plan matches the backend truth source.
- One image per card is enough; reversed readings can reuse the same artwork and rotate it 180 degrees in UI or post-processing.

## 2. Deck-Wide Style Lock

- Visual direction: mystical Art Nouveau tarot, symbolic but readable, elegant and ceremonial rather than horror or hyper-real photo.
- Rendering: detailed gouache-and-ink digital painting, luminous jewel tones, subtle parchment grain, clean silhouettes, polished ornamental frame.
- Composition: single focal scene, centered hierarchy, generous negative space around the main figure, strong symbolic props, no cluttered backgrounds.
- Output: vertical `2:3` ratio, recommended `1024x1536`, PNG, no title text baked into the card so UI can control typography later.
- Consistency rule: keep the same model, same sampler, same prompt prefix, same negative prompt, and the same frame language across all 78 cards.

### Base Style Prompt

```text
vertical 2:3 tarot card illustration, cohesive full-deck art direction, mystical art nouveau fantasy, detailed gouache and ink painting, luminous jewel tones, antique gold filigree, elegant celestial border, centered symbolic composition, soft parchment texture, cinematic rim light, polished storytelling illustration, highly readable silhouette, sacred and contemplative mood, no card title text, no watermark, no logo, no modern props, no sci-fi elements
```

### Shared Negative Prompt

```text
blurry, low detail, noisy image, muddy colors, extra limbs, extra fingers, duplicated objects, deformed anatomy, cropped face, cut-off hands, unreadable symbolism, busy background, collage, photorealism, 3d render, comic panel layout, modern city, neon cyberpunk, typography, watermark, logo, frame mismatch
```

### Recommended Consistency Workflow

1. Generate 4 anchor cards first: `major-fool`, `major-high-priestess`, `major-death`, `cups-ace`.
2. Lock the border, brushwork, lighting, and figure proportions from those anchors before batch generation.
3. Use file names identical to backend `card_code`, for example `major-fool.png` and `wands-ace.png`.
4. Keep scene prompts specific, but do not change the base style prompt between cards.
5. If your image model supports style reference or character reference, reuse the same border/frame reference across all cards.

### Prompt Formula

```text
[Base Style Prompt], [Card Scene Prompt], [optional palette accent], [Shared Negative Prompt]
```

### Example Final Prompt

```text
vertical 2:3 tarot card illustration, cohesive full-deck art direction, mystical art nouveau fantasy, detailed gouache and ink painting, luminous jewel tones, antique gold filigree, elegant celestial border, centered symbolic composition, soft parchment texture, cinematic rim light, polished storytelling illustration, highly readable silhouette, sacred and contemplative mood, no card title text, no watermark, no logo, no modern props, no sci-fi elements, The Fool, a youthful traveler stepping toward a cliff edge with a small satchel, white rose in hand, loyal white dog at their side, bright dawn sky, distant mountains, feeling of wonder, trust, and open possibility, palette accent of sunrise gold and airy sky blue, blurry, low detail, noisy image, muddy colors, extra limbs, extra fingers, duplicated objects, deformed anatomy, cropped face, cut-off hands, unreadable symbolism, busy background, collage, photorealism, 3d render, comic panel layout, modern city, neon cyberpunk, typography, watermark, logo, frame mismatch
```

## 3. Major Arcana

Palette accent: midnight blue, ivory, antique gold, with each card's symbolic accent color.

- `major-fool` / `The Fool`: `The Fool, a youthful traveler stepping toward a cliff edge with a small satchel, white rose in hand, loyal white dog at their side, bright dawn sky, distant mountains, feeling of wonder, trust, and open possibility`
- `major-magician` / `The Magician`: `The Magician at a ritual altar, one wand raised to the sky and one hand pointing downward, cup sword wand and pentacle laid before them, infinity symbol above the head, roses and lilies around the scene, radiant focus and manifestation`
- `major-high-priestess` / `The High Priestess`: `The High Priestess seated between black and white pillars, crescent moon at her feet, veil of pomegranates behind her, sacred scroll in hand, moonlit silence, hidden knowledge, serene intuition`
- `major-empress` / `The Empress`: `The Empress on a cushioned throne in a lush meadow, crown of stars, wheat field and flowing river nearby, venus motif, abundant garden, maternal warmth, creative fertility, rich natural beauty`
- `major-emperor` / `The Emperor`: `The Emperor seated on a stone throne carved with ram heads, scepter and orb in hand, red robes over armor, stern mountains behind, ordered structure, authority, stability, disciplined power`
- `major-hierophant` / `The Hierophant`: `The Hierophant on a temple throne giving a blessing, two acolytes kneeling before him, crossed keys below, sacred architecture, tradition, teaching, ritual wisdom`
- `major-lovers` / `The Lovers`: `The Lovers with two figures beneath a radiant angel, mountain peak behind, fruit tree and fiery tree on either side, open sky, union, choice, values aligned with the heart`
- `major-chariot` / `The Chariot`: `The Chariot with a victorious charioteer under a starry canopy, black and white sphinxes drawing the chariot, city walls behind, forward movement, resolve, controlled momentum`
- `major-strength` / `Strength`: `Strength as a calm woman gently opening a lion's jaws, infinity symbol above her head, white gown, flowers and greenery around, gentle mastery, inner courage, emotional steadiness`
- `major-hermit` / `The Hermit`: `The Hermit standing alone on a snowy mountain peak, lantern glowing in one hand, staff in the other, deep blue night, solitude, introspection, quiet guidance`
- `major-wheel-of-fortune` / `Wheel of Fortune`: `Wheel of Fortune as a giant celestial wheel turning in clouds, sphinx at the top, serpent descending, winged beings reading in the corners, fate, cycles, turning points, sacred motion`
- `major-justice` / `Justice`: `Justice seated upright on a throne between red drapes, sword held vertically in one hand and balanced scales in the other, symmetrical composition, truth, fairness, accountability`
- `major-hanged-man` / `The Hanged Man`: `The Hanged Man suspended by one foot from a living tree, glowing halo around the head, calm expression, still air, surrender, altered perspective, suspended wisdom`
- `major-death` / `Death`: `Death as a skeletal rider on a white horse carrying a black banner with a white rose, fallen crown on the ground, river and dawn on the horizon, transformation, necessary ending, solemn release`
- `major-temperance` / `Temperance`: `Temperance as an angel pouring water between two cups, one foot on land and one in a stream, irises in bloom, golden crown in the distance, balance, healing, measured flow`
- `major-devil` / `The Devil`: `The Devil enthroned on a dark pedestal, horned figure above two loosely chained humans, torchlit cavern atmosphere, temptation, bondage, shadow attachment, oppressive glamour`
- `major-tower` / `The Tower`: `The Tower struck by lightning, crown blasted from the top, flames bursting from windows, figures falling through storm clouds, sudden revelation, collapse of false structure, violent truth`
- `major-star` / `The Star`: `The Star with a kneeling figure pouring water into a pool and onto the earth, giant eight-pointed star above, smaller stars surrounding it, ibis nearby, hope, renewal, soft celestial calm`
- `major-moon` / `The Moon`: `The Moon above twin towers, a wolf and dog howling on either side of a winding path, crayfish emerging from a pool, misty blue night, dreams, illusion, uncertainty, subconscious pull`
- `major-sun` / `The Sun`: `The Sun with a radiant child riding a white horse, red banner flowing, giant sun overhead, sunflowers behind a stone wall, joy, warmth, clarity, open vitality`
- `major-judgement` / `Judgement`: `Judgement as an angel sounding a trumpet from the clouds, people rising from coffins with uplifted arms, mountains in the distance, awakening, absolution, decisive calling`
- `major-world` / `The World`: `The World with a dancing figure inside a laurel wreath, wand in each hand, bull eagle lion and angel in the four corners, completion, harmony, integrated wholeness`

## 4. Cups

Palette accent: pearl teal, moon silver, sea-glass cyan, soft rose light.

- `cups-ace` / `Ace of Cups`: `Ace of Cups, an overflowing chalice hovering above a lotus pond, five streams of water pouring down, white dove descending with sacred light, emotional renewal, blessing, open heart`
- `cups-2` / `Two of Cups`: `Two of Cups, two figures facing each other and exchanging golden cups, winged lion and caduceus floating above them, mutual recognition, partnership, balanced affection`
- `cups-3` / `Three of Cups`: `Three of Cups, three women in flowing dresses raising their cups in celebration, harvest fruit and flowers at their feet, friendship, joy, communal abundance`
- `cups-4` / `Four of Cups`: `Four of Cups, a seated figure beneath a tree with arms crossed, three cups before them and a fourth offered from a cloud, contemplation, withdrawal, unnoticed opportunity`
- `cups-5` / `Five of Cups`: `Five of Cups, a cloaked figure mourning three spilled cups while two upright cups remain behind, river and bridge leading to a distant home, grief, regret, surviving hope`
- `cups-6` / `Six of Cups`: `Six of Cups, a gentle courtyard scene where one child offers a cup of flowers to another, old buildings behind, nostalgia, innocence, tender memory`
- `cups-7` / `Seven of Cups`: `Seven of Cups, a figure gazing at seven floating cups containing jewels, snake, laurel wreath, dragon, castle, shrouded figure, dream choice, fantasy, overwhelming possibilities`
- `cups-8` / `Eight of Cups`: `Eight of Cups, a lone traveler walking away from a stack of cups beneath an eclipsed moon, rocky mountains ahead, leaving what no longer satisfies, searching for deeper meaning`
- `cups-9` / `Nine of Cups`: `Nine of Cups, a satisfied host seated proudly before a curved display of nine cups, rich fabrics, fulfilled wish, comfort, emotional contentment`
- `cups-10` / `Ten of Cups`: `Ten of Cups, a family standing together beneath a rainbow arch of ten golden cups, children playing, green meadow, river and home, harmony, lasting happiness, shared fulfillment`
- `cups-page` / `Page of Cups`: `Page of Cups, a youthful messenger in blue holding a cup with a fish emerging from it, shoreline behind, playful intuition, emotional curiosity, surprising inspiration`
- `cups-knight` / `Knight of Cups`: `Knight of Cups, an armored rider on a calm white horse carrying a silver cup, slow river and gentle hills nearby, romance, idealism, graceful pursuit`
- `cups-queen` / `Queen of Cups`: `Queen of Cups, a queen seated on an ornate throne by the sea, holding a closed ceremonial cup, shell motifs and calm tides around her, empathy, intuition, deep feeling`
- `cups-king` / `King of Cups`: `King of Cups, a king on a stone throne floating over choppy water, cup in one hand and scepter in the other, ship and fish in the waves, emotional mastery, composed compassion`

## 5. Wands

Palette accent: ember orange, warm gold, sunlit ochre, crimson flame.

- `wands-ace` / `Ace of Wands`: `Ace of Wands, a hand emerging from a cloud holding a budding wand, sparks of life around the branch, bright sky and distant hills, creative ignition, bold beginning`
- `wands-2` / `Two of Wands`: `Two of Wands, a figure standing on battlements holding a globe and looking over sea and land, one wand in hand and one fixed behind, planning, range, future vision`
- `wands-3` / `Three of Wands`: `Three of Wands, a cloaked figure on a hill watching ships travel across open water, three planted wands nearby, expansion, foresight, opportunities unfolding`
- `wands-4` / `Four of Wands`: `Four of Wands, four decorated wands forming a garlanded gateway, dancers celebrating before a distant castle, stable joy, welcome, milestone celebration`
- `wands-5` / `Five of Wands`: `Five of Wands, five youths crossing staves in chaotic competition, dust and movement everywhere, conflict, friction, energetic struggle without fatal harm`
- `wands-6` / `Six of Wands`: `Six of Wands, a rider wearing a laurel crown on horseback, holding a decorated wand while a crowd looks on, recognition, public victory, earned confidence`
- `wands-7` / `Seven of Wands`: `Seven of Wands, a figure on higher ground defending with one wand against six rising from below, windswept stance, courage under pressure, holding one's ground`
- `wands-8` / `Eight of Wands`: `Eight of Wands, eight staffs streaking diagonally through open sky over a river valley, swift movement, acceleration, events rushing toward resolution`
- `wands-9` / `Nine of Wands`: `Nine of Wands, a weary bandaged figure gripping one wand while eight stand behind like a fence, guarded posture, resilience, fatigue, readiness to endure`
- `wands-10` / `Ten of Wands`: `Ten of Wands, a person bent under the weight of ten bundled staffs while walking toward a town, burden, overcommitment, final push under pressure`
- `wands-page` / `Page of Wands`: `Page of Wands, a bright-eyed youth in a desert holding a sprouting wand, wind catching the tunic, adventurous energy, curiosity, early confidence`
- `wands-knight` / `Knight of Wands`: `Knight of Wands, a fierce rider on a rearing horse charging forward with a flaming wand, desert winds and speed lines in the dust, passion, impulse, daring motion`
- `wands-queen` / `Queen of Wands`: `Queen of Wands, a confident queen on a sunflower throne with a black cat at her feet, flowering wand in hand, charismatic warmth, creative authority`
- `wands-king` / `King of Wands`: `King of Wands, a commanding king on a salamander-carved throne holding a flowering wand, desert horizon behind, visionary leadership, bold execution`

## 6. Swords

Palette accent: steel blue, moon gray, silver white, storm-cloud indigo.

- `swords-ace` / `Ace of Swords`: `Ace of Swords, a hand rising from a cloud and lifting a gleaming upright sword crowned with laurel and gold, crisp mountain air, clarity, truth, decisive breakthrough`
- `swords-2` / `Two of Swords`: `Two of Swords, a blindfolded figure seated by the sea with two crossed swords over the chest, crescent moon in the night sky, stalemate, guarded mind, suspended choice`
- `swords-3` / `Three of Swords`: `Three of Swords, a red heart pierced by three blades against a stormy rain-filled sky, heartbreak, painful truth, emotional rupture`
- `swords-4` / `Four of Swords`: `Four of Swords, a resting knight carved in a chapel tomb, three swords hanging above and one laid below, candlelit stillness, recovery, pause, sacred rest`
- `swords-5` / `Five of Swords`: `Five of Swords, a smug figure gathering swords while two defeated people walk away near a gray shoreline, hollow victory, conflict, moral cost`
- `swords-6` / `Six of Swords`: `Six of Swords, a small boat crossing calm water with a ferryman, cloaked passenger and child, six swords standing in the boat, transition, departure, moving toward peace`
- `swords-7` / `Seven of Swords`: `Seven of Swords, a stealthy figure carrying five swords away from a military camp while two remain behind, strategy, secrecy, evasion, uneasy cleverness`
- `swords-8` / `Eight of Swords`: `Eight of Swords, a blindfolded bound woman surrounded by eight swords in muddy ground, open path still visible beyond, trapped perception, anxiety, self-limitation`
- `swords-9` / `Nine of Swords`: `Nine of Swords, a person sitting upright in bed with face in hands while nine swords hang on a dark wall, nightmare, guilt, sleepless worry`
- `swords-10` / `Ten of Swords`: `Ten of Swords, a fallen figure pierced by ten blades at the end of a black night while dawn begins at the horizon, collapse, finality, painful ending before renewal`
- `swords-page` / `Page of Swords`: `Page of Swords, an alert youth on a windy hill holding a raised sword, clouds racing overhead, sharp curiosity, vigilance, restless intellect`
- `swords-knight` / `Knight of Swords`: `Knight of Swords, an armored rider charging through storm and wind with sword extended, horse in full motion, forceful thought, speed, uncompromising action`
- `swords-queen` / `Queen of Swords`: `Queen of Swords, a stern queen on a clouded throne holding her sword upright while extending one hand, clear boundary, discernment, cool intelligence`
- `swords-king` / `King of Swords`: `King of Swords, a king on a butterfly-carved throne with a straight sword and steady gaze, storm clouds behind but posture unmoved, logic, authority, just judgment`

## 7. Pentacles

Palette accent: olive green, harvest amber, moss, earth gold.

- `pentacles-ace` / `Ace of Pentacles`: `Ace of Pentacles, a hand emerging from a cloud offering a glowing golden pentacle above a garden arch and mountain path, tangible opportunity, grounded blessing, prosperity seed`
- `pentacles-2` / `Two of Pentacles`: `Two of Pentacles, a juggler balancing two pentacles linked by an infinity ribbon while ships rise on rough waves behind, adaptability, balance, playful management`
- `pentacles-3` / `Three of Pentacles`: `Three of Pentacles, a craftsperson showing detailed stonework inside a cathedral to a monk and architect, teamwork, skill, collaborative building`
- `pentacles-4` / `Four of Pentacles`: `Four of Pentacles, a seated figure tightly holding pentacles at chest, head, and feet with a city in the background, security, control, possessiveness`
- `pentacles-5` / `Five of Pentacles`: `Five of Pentacles, two struggling figures walking through snow outside a glowing stained-glass window, hardship, exclusion, ignored sanctuary`
- `pentacles-6` / `Six of Pentacles`: `Six of Pentacles, a wealthy figure with scales distributing coins to kneeling people, fair exchange, generosity, uneven power dynamics made visible`
- `pentacles-7` / `Seven of Pentacles`: `Seven of Pentacles, a gardener leaning on a staff and studying pentacles growing on a vine, patient assessment, investment, waiting for results`
- `pentacles-8` / `Eight of Pentacles`: `Eight of Pentacles, a focused artisan seated at a workbench carving pentacles one by one, disciplined craft, repetition, mastery through effort`
- `pentacles-9` / `Nine of Pentacles`: `Nine of Pentacles, an elegant figure in a vineyard with a falcon on one hand and pentacles among the vines, self-sufficiency, cultivated abundance, refined independence`
- `pentacles-10` / `Ten of Pentacles`: `Ten of Pentacles, an elder beneath an archway watching a family with dogs in a prosperous courtyard, pentacles woven through the architecture, legacy, stability, generational wealth`
- `pentacles-page` / `Page of Pentacles`: `Page of Pentacles, a young scholar standing in a green field and studying a single pentacle with full attention, grounded ambition, practical learning, first real step`
- `pentacles-knight` / `Knight of Pentacles`: `Knight of Pentacles, a steadfast rider on a heavy dark horse holding a pentacle over ploughed earth, patience, discipline, dependable progress`
- `pentacles-queen` / `Queen of Pentacles`: `Queen of Pentacles, a queen seated in a lush garden holding a pentacle on her lap, rabbit near the throne, comfort, nurturing practicality, embodied abundance`
- `pentacles-king` / `King of Pentacles`: `King of Pentacles, a richly robed king on a vine-covered throne with bull motifs, pentacle in one hand and scepter in the other, grounded power, financial mastery, stable stewardship`

## 8. Suggested Next Step

- If you later want this to plug directly into generation tooling, the next practical artifact is a machine-readable `tarot_image_prompts.json` keyed by `card_code`, generated from this document.
