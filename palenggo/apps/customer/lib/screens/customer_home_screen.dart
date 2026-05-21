import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:palenggo_shared/palenggo_shared.dart';
import 'package:uuid/uuid.dart';

/// Phase 1 step 4 (spec §12): browse markets/stalls → cart → drop pin +
/// landmark note → GCash QR placeholder checkout.
class CustomerHomeScreen extends ConsumerStatefulWidget {
  const CustomerHomeScreen({super.key});

  @override
  ConsumerState<CustomerHomeScreen> createState() =>
      _CustomerHomeScreenState();
}

class _CustomerHomeScreenState extends ConsumerState<CustomerHomeScreen> {
  final _landmarkController =
      TextEditingController(text: 'Blue gate beside sari-sari store');
  final List<OrderItem> _cart = [];

  @override
  void dispose() {
    _landmarkController.dispose();
    super.dispose();
  }

  void _addToCart(Product product) {
    setState(() {
      _cart.add(OrderItem(
        productId: product.id,
        name: product.name,
        quantity: 1,
        unitPrice: product.pricePerUnit,
      ));
    });
  }

  void _checkout() {
    final repo = ref.read(palenggoRepositoryProvider);
    final order = Order(
      id: 'PAL-${const Uuid().v4().substring(0, 8)}',
      customerId: 'customer_demo',
      stallId: 'stall_47',
      status: OrderStatus.pending,
      items: List.of(_cart),
      deliveryFee: 50,
      // Carbon Market, Cebu City — placeholder until Maps pin-drop is wired.
      deliveryLat: 10.3157,
      deliveryLng: 123.8854,
      landmarkNote: _landmarkController.text,
    );
    repo.createOrder(order);
    setState(_cart.clear);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Order ${order.id} submitted. GCash QR placeholder generated.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final region = ref.watch(regionConfigProvider);
    final repo = ref.watch(palenggoRepositoryProvider);
    final products = repo.listProducts();
    final cartTotal =
        _cart.fold<double>(0, (sum, item) => sum + item.subtotal);

    return Scaffold(
      appBar: AppBar(
        title: Text(region.appName),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => ref.read(authRepositoryProvider).signOut(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Nearby market: Carbon Market',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          const Text("Browse today's fresh stall photos and prices."),
          const SizedBox(height: 12),
          ...products.map(
            (p) => Card(
              child: ListTile(
                leading: const CircleAvatar(child: Icon(Icons.set_meal)),
                title: Text(
                  '${p.name} — ${region.currencySymbol}'
                  '${p.pricePerUnit.toStringAsFixed(0)}/${p.unit}',
                ),
                subtitle: Text(
                  'Stall 47 • '
                  '${p.quantityAvailable.toStringAsFixed(0)} ${p.unit} '
                  'available',
                ),
                trailing: FilledButton(
                  onPressed: () => _addToCart(p),
                  child: const Text('Add'),
                ),
              ),
            ),
          ),
          const Divider(),
          Text(
            'Cart total: ${region.currencySymbol}${cartTotal.toStringAsFixed(0)} '
            '+ ${region.currencySymbol}50 delivery',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          TextField(
            controller: _landmarkController,
            decoration:
                const InputDecoration(labelText: 'Required landmark note'),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _cart.isEmpty ? null : _checkout,
            icon: const Icon(Icons.qr_code),
            label: const Text('Checkout with GCash QR'),
          ),
        ],
      ),
    );
  }
}
