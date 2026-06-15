import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getSchedules, confirmPresence, leaveParty, cancelSchedule, setMyCharacter,
  promoteColeader, kickMember,
} from "../lib/api";
import { qk } from "../lib/queryKeys";

// Encapsula a lista de PTs do usuário + as mutações comuns, todas invalidando o cache.
export function usePartySchedules() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.schedules });
    qc.invalidateQueries({ queryKey: qk.calendar });
  };

  const query = useQuery({ queryKey: qk.schedules, queryFn: getSchedules });

  return {
    schedules: query.data ?? [],
    isLoading: query.isLoading,
    confirm:    useMutation({ mutationFn: (id: number) => confirmPresence(id), onSuccess: invalidate }),
    leave:      useMutation({ mutationFn: (id: number) => leaveParty(id), onSuccess: invalidate }),
    cancel:     useMutation({ mutationFn: (id: number) => cancelSchedule(id), onSuccess: invalidate }),
    setChar:    useMutation({ mutationFn: (v: { id: number; characterId: number }) => setMyCharacter(v.id, v.characterId), onSuccess: invalidate }),
    promote:    useMutation({ mutationFn: (v: { id: number; uid: string; co: boolean }) => promoteColeader(v.id, v.uid, v.co), onSuccess: invalidate }),
    kick:       useMutation({ mutationFn: (v: { id: number; uid: string }) => kickMember(v.id, v.uid), onSuccess: invalidate }),
    invalidate,
  };
}
