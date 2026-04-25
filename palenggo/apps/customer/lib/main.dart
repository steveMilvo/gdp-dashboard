import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';

import 'firebase_options.dart';

Future<void> main() async {
  await bootstrapFirebase(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const ProviderScope(child: _CustomerApp()));
}

class _CustomerApp extends ConsumerWidget {
  const _CustomerApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'PalengGo',
      debugShowCheckedModeBanner: false,
      theme: PalengGoTheme.light(),
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends ConsumerWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    return auth.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(body: Center(child: Text('$e'))),
      data: (user) => user == null
          ? const PhoneOtpScreen(appLabel: 'Customer')
          : const _CustomerHomePlaceholder(),
    );
  }
}

class _CustomerHomePlaceholder extends ConsumerWidget {
  const _CustomerHomePlaceholder();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PalengGo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
          ),
        ],
      ),
      // Phase 1 next step: replace with markets map + browse + cart + pin/landmark
      // checkout. See spec §12 Phase 1, step 4.
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Signed in. Market browse + landmark checkout comes next.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
