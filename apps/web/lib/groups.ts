import type { Group } from './api';

export type ShelfGroup = Group & { kind: 'shelves' | 'collections' };
export function allShelves(shelves: Group[] = [], collections: Group[] = []): ShelfGroup[] {
  return [
    ...shelves.map((g) => ({ ...g, kind: 'shelves' as const })),
    ...collections.map((g) => ({ ...g, kind: 'collections' as const })),
  ];
}
export function destinationData(value: string): Record<string, string> {
  const [kind, id] = value.split(':');
  return id && ['shelves', 'collections'].includes(kind)
    ? { [kind === 'shelves' ? 'shelf_id' : 'collection_id']: id }
    : {};
}
