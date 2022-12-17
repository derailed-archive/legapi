# Derailed

Welcome! This is the Derailed monorepo, a home for anything related to the Derailed Codebase.
This mainly talks about technical, or otherwise coding-related aspects so I'd suggest you to go somewhere else for a friendly outsider overview.

## Running Derailed

Running Derailed is quite a task.
While we've tried and are trying to make it easy, it still has a lot of requirements.
The biggest one being a database.

Derailed uses MongoDB as our DB, so you'll first want to launch an instance of it in whatever way you wish.
After launching, obtain the uri of said db then continue.

After setting up the database, you'll want to make a file named `.env` in the same directory which Derailed is in then continue.

One you've made your `.env` file, type `MONGO_URI=` and your uri, like so:

```
MONGO_URL=mongo
```

Now with that, you can finally run the `start.py` file in the same directory and use your Derailed instance.

### ⚠️ WARNING ⚠️

If you are serious about rate limit protection, please look every step possible into adding redis to your instance to increase scalability, speed, and distributability.

### Scaling with Redis

Derailed supports redis as a second option for caching and primary option for rate limiting.
Meaning you can use redis to further scale your Derailed instance!

The first thing you'll want to do is setup a redis instance, once you've launched an instance of it, like when setting up MongoDB, get its uri then continue.

Once you've got its uri, you can firmly add it as a ENV variable like on the MongoDB example except for replacing `MONGO_URI` with `REDIS_URI`.

## Meta

### Versioning

We currently follow no external versioning style to make development easier. In the future we may adopt one in which it it most likely will be like Discord's API Versioning.

Internally though, we may use versioning. Like we may release Discoursy 0.1 to coinside new features and bug fixes.
In that case, we may use only semver.

### The Goal

The deterministic goal for Derailed is to become better than Discord,
but for now, our goal is to make a minimal platform which people can and want to use.

The entire scope of things will be detailed in our 2023 plan soon.
