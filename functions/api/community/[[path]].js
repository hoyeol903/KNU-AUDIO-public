import { handleCommunity } from '../../../community/api.mjs';
export function onRequest({request, env}) { return handleCommunity(request, env); }
