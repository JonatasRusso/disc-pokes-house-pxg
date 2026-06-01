import { useQuery } from "@tanstack/react-query";
import { getMe, User } from "./api";

export function useAuth() {
  const { data: user, isLoading, error } = useQuery<User, Error>({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });
  return { user: user ?? null, isLoading, isLoggedIn: !!user };
}
