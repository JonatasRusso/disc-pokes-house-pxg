// Chaves centralizadas do React Query — evita strings repetidas e o bug clássico
// de cache não invalidado por key divergente.
export const qk = {
  schedules:  ["schedules"] as const,
  calendar:   ["calendar"] as const,
  freeSlots:  ["free-slots"] as const,
  characters: ["characters"] as const,
  members:    ["members"] as const,
  pokemon:    ["pokemon"] as const,
  myPokemon:  ["pokemon", "my"] as const,
  me:         ["me"] as const,
  history:    ["history"] as const,
};
