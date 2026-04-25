import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';

import 'firebase_options.dart';

Future<void> main() async {
  await bootstrapFirebase(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const ProviderScope(child: _RiderApp()));
}

class _RiderApp extends ConsumerWidget {
  const _RiderApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'PalengGo Rider',
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
          ? const PhoneOtpScreen(appLabel: 'Rider')
          : const _RiderHomePlaceholder(),
    );
  }
}

class _RiderHomePlaceholder extends ConsumerWidget {
  const _RiderHomePlaceholder();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PalengGo Rider'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
          ),
        ],
      ),
      // Phase 1 next step: AVAILABLE toggle + first-to-accept order queue +
      // navigation. See spec §12 Phase 1, step 5.
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Signed in. Available toggle + order acceptance comes next.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
