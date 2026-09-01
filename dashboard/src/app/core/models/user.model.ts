// Mirrors app/api/schemas.py's UserOut.
export interface User {
  id: number;
  email: string;
  name: string | null;
  avatarUrl: string | null;
  isOwner: boolean;
}
