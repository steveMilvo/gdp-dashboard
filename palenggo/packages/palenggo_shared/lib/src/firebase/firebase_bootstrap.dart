import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/widgets.dart';

/// Initializes Firebase for any of the three apps.
///
/// Each app must run `flutterfire configure` to generate
/// `lib/firebase_options.dart`. Pass that file's `DefaultFirebaseOptions.currentPlatform`
/// in via [options] from the app's `main()`. See SETUP.md.
Future<void> bootstrapFirebase({required FirebaseOptions options}) async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: options);
}
