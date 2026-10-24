# NeuralRoute 3D — Inside an Intelligent AI Router

An educational simulator showing how a small feedforward neural network decides
whether an AI request should go to a Small, Medium, or Large model.

This project is standalone. It does not depend on or modify ThermalLoop AI Center.

## Status

This is an **in-progress build**. Read this section before relying on the project.

### Implemented and verified (30 unit tests passing)

| Area | File | Verification |
|---|---|---|
| Deterministic feature extraction (6 heuristic features, fixed normalization caps) | `src/ml/features.ts` | unit tests |
| Real MLP 6→8→6→3: ReLU hidden layers, softmax output | `src/ml/mlp.ts` | forward pass checked against an independent reimplementation |
| Categorical cross-entropy, manual backprop, Adam, seeded shuffling | `src/ml/mlp.ts` | **backprop gradient checked against finite differences** |
| Reproducible training (same seed → identical weights) | `src/ml/mlp.ts` | unit test |
| Best-epoch selection (`restoreBest`) | `src/ml/mlp.ts` | unit test: returned weights match the lowest validation loss |
| Confusion matrix, model file validation | `src/ml/mlp.ts` | unit tests |
| Labeled dataset: 72 prompts, 24 per class, stratified 54/18 split | `src/data/dataset.ts` | balance test + leakage test (max cross-split Jaccard 0.375 < 0.5) |
| Bundled demo weights (`npm run train:demo`, best epoch 155) | `src/ml/demoWeights.json` | loaded and used in tests |
| Inference facade: features, pre/post activations, logits, probabilities, route | `src/ml/index.ts` | tests |
| Routing policy (classifier argmax) separate from rule-based baseline | `src/ml/routing.ts` | tests |
| Energy-aware strategy simulation (A/B/C), labeled Simulated | `src/sim/energy.ts` | tests |
| Web app (React): network view with selection, neuron and connection inspector, full weight matrix, what-if sliders, two-prompt comparison, in-browser training, save/load model, confusion matrix, energy table, keyboard access, reduce-motion and low-quality toggles | `src/app/*.tsx` | bundled with esbuild (`npm run build:app`); **server-side render check passes**; **checked in headless Chromium**: all panels render, neuron and connection inspectors work, Run/speed/step controls work, prompt edits re-run inference, what-if and in-browser training work, Stop ends training mid-run, no console errors, no horizontal overflow at 390 px width |

Type-checking: the core modules pass `tsc --strict --noUnusedLocals --noUnusedParameters`. The `scripts/` files need `@types/node`, which is listed in `devDependencies` and is only missing in the environment that produced this code.

### Not yet built or not verified

- **The 3D view.** The network is a 2D SVG with glow. Three.js, React Three Fiber, bloom, and camera controls are not included.
- **Visual polish** has been checked only in screenshots, not on real devices or other browsers.
- **TensorFlow.js.** The network is plain TypeScript. Its weight layout (`kernel[in][out]`) matches a TF.js `Dense` layer, but no TF.js model is wired up or tested. The spec asks for TF.js; this is a deviation.
- **Test-framework and charts.** Tests use the Node test runner, not Vitest; charts are hand-drawn SVG, not Recharts.
- **Vite and Vercel config.** The build uses esbuild, which outputs static files that can be hosted on Vercel or Netlify.

### Known limitations

- **Validation is used for model selection**, so the validation accuracy reported for the bundled model (83.3% on 18 examples) is optimistically biased. There is no separate test set. The confusion matrix shows the main error is Small prompts predicted as Medium.
- Labels are assigned by hand using simple criteria. They are not validated against model quality or cost.
- The six features are keyword and surface heuristics. They do not understand prompts, and wording alone can change the route.
- The bundled classifier is **educational, not a validated production router.**

## Commands

```bash
npm run train:demo   # retrain the demo classifier -> src/ml/demoWeights.json
npm test             # run the 30 unit tests (Node test runner + tsx)
npm run build:app    # bundle the web app into ONE file: dist/neuralroute3d.html
npm run preview      # write neuralroute3d-preview.html (static report from the real pipeline)
npm run typecheck    # tsc --noEmit (requires typescript and @types/node installed)
```

## Blocker in the build environment

`npm install` could not run in the environment that produced this code. The
egress proxy refused connections to `registry.npmjs.org` with a 403, and the
response said the host is not on this session's allowlist. The required packages
(Vite, Three.js, React Three Fiber, TensorFlow.js, Vitest, Recharts) therefore
could not be installed, and the UI could not be built or tested.

To continue, allow `registry.npmjs.org` for this session (in claude.ai under
Settings → Capabilities, if your plan permits it), then run:

```bash
npm install
npm run test
```

## Next steps (in order)

1. Run `npm install`, `npm test`, `npm run build:app` on a machine with registry access, and open `dist/neuralroute3d.html` in a browser to check the layout and interactions.
2. Add the 3D view (React Three Fiber) with the same selection and stage data.
3. Add TF.js parity tests: load `demoWeights.json` into a `tf.sequential` model and check that its outputs match `forwardTrace`.
4. Move training to a Web Worker if larger datasets make it slow.
5. Add a held-out test split so that validation accuracy is not used for model selection.
