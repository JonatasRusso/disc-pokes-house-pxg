import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCharacters, createCharacter, updateCharacter, deleteCharacter } from "../lib/api";
import { qk } from "../lib/queryKeys";

// Encapsula listagem + CRUD de personagens com invalidação automática do cache.
export function useCharacters() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: qk.characters });

  const query  = useQuery({ queryKey: qk.characters, queryFn: getCharacters });
  const create = useMutation({ mutationFn: (name: string) => createCharacter({ name }), onSuccess: invalidate });
  const update = useMutation({ mutationFn: (v: { id: number; name: string }) => updateCharacter(v.id, { name: v.name }), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => deleteCharacter(id), onSuccess: invalidate });

  return {
    characters: query.data ?? [],
    isLoading: query.isLoading,
    create, update, remove,
  };
}
