import type { Sample } from './bench';

interface ImageInfo {
  id?: string;
  '@id'?: string;
  type?: string;
  profile?: unknown;
  width: number;
  height: number;
}

const infoCache = new Map<string, Promise<ImageInfo>>();

function imageInfo(url: string): Promise<ImageInfo> {
  if (!infoCache.has(url)) {
    infoCache.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`Image information returned ${r.status}`);
        return r.json();
      })
    );
  }
  return infoCache.get(url)!;
}

export async function folioView(sample: Sample, label: string) {
  const info = await imageInfo(sample.image);
  // CSNTM answers info.json only at the plain URL; its tokenized id serves the image itself.
  const service = sample.image.replace(/\/info\.json$/, '');
  const resolved = (info.id ?? info['@id'] ?? service).replace(/\/$/, '');
  const { width, height } = info;
  const id = `urn:paleo-bench:${sample.id}`;
  const manifest = {
    '@context': 'http://iiif.io/api/presentation/3/context.json',
    id,
    type: 'Manifest',
    label: { none: [label] },
    items: [
      {
        id: `${id}:canvas`,
        type: 'Canvas',
        width,
        height,
        items: [
          {
            id: `${id}:page`,
            type: 'AnnotationPage',
            items: [
              {
                id: `${id}:image`,
                type: 'Annotation',
                motivation: 'painting',
                target: `${id}:canvas`,
                body: {
                  id: `${resolved}/full/max/0/default.jpg`,
                  type: 'Image',
                  format: 'image/jpeg',
                  width,
                  height,
                  service: [
                    {
                      id: service,
                      type: info.type ?? (info['@id'] ? 'ImageService2' : 'ImageService3'),
                      profile: info.profile
                    }
                  ]
                }
              }
            ]
          }
        ]
      }
    ]
  };
  const half = Math.round(width / 2);
  const region =
    sample.side === 'verso'
      ? { x: 0, y: 0, width: half, height }
      : sample.side === 'recto'
        ? { x: half, y: 0, width: width - half, height }
        : null;
  return { id, manifest, region };
}
