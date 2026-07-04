import crypto from 'crypto';

const sk  = crypto.randomBytes(32).toString('hex');
console.log(sk);