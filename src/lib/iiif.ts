/**
 * Build a IIIF Presentation API v3 manifest from an array of info.json URLs.
 * Each info.json URL becomes a canvas in the manifest.
 */
export function buildManifest(
	items: { label: string; infoJsonUrl: string }[],
	manifestLabel = 'Paleo Bench Images'
) {
	return {
		'@context': 'http://iiif.io/api/presentation/3/context.json',
		id: 'urn:paleo-bench:manifest',
		type: 'Manifest',
		label: { en: [manifestLabel] },
		items: items.map((item, i) => {
			const serviceUrl = item.infoJsonUrl.replace(/\/info\.json$/, '');
			return {
				id: `urn:paleo-bench:canvas:${i}`,
				type: 'Canvas',
				label: { en: [item.label] },
				width: 4000,
				height: 6000,
				items: [
					{
						id: `urn:paleo-bench:canvas:${i}:page`,
						type: 'AnnotationPage',
						items: [
							{
								id: `urn:paleo-bench:canvas:${i}:page:annotation`,
								type: 'Annotation',
								motivation: 'painting',
								target: `urn:paleo-bench:canvas:${i}`,
								body: {
									id: `${serviceUrl}/full/max/0/default.jpg`,
									type: 'Image',
									format: 'image/jpeg',
									service: [
										{
											id: serviceUrl,
											type: 'ImageService3',
											profile: 'level2'
										}
									]
								}
							}
						]
					}
				]
			};
		})
	};
}

/**
 * Build a single-canvas manifest for one info.json URL.
 */
export function buildSingleManifest(label: string, infoJsonUrl: string) {
	return buildManifest([{ label, infoJsonUrl }], label);
}
